"""Qwen-72B distillation pass — generate judge-style CoT for Dataset B narratives.

Pipeline:
  1. Load Dataset B (narratives with hidden ground-truth labels).
  2. For each row, sample n completions from Qwen2.5-72B-Instruct
     (self-consistency).
  3. Parse the verdict from each completion ("verdict: fraud" / "not_fraud").
  4. Majority-vote across the n samples; pick the CoT from the modal cluster.
  5. Filter: keep only rows where Qwen-verdict == ground-truth label
     AND self-consistency >= MIN_AGREEMENT (default 2 of 3).
  6. Write the SFT-ready parquet.

Resumable: every API completion is appended to a JSONL log keyed by
(data_uuid, sample_idx). On restart we skip pairs already in the log.

API: any OpenAI-compatible chat completions endpoint. Defaults to Together.ai.

Usage:
  # 0. Set API key:
  #     PowerShell:  $env:TOGETHER_API_KEY = "..."
  #     Bash:        export TOGETHER_API_KEY=...

  # 1. Smoke test (10 rows, n=2) to verify prompt + parsing:
  python -m src.sft_v3.qwen_distill --smoke-test

  # 2. Full run:
  python -m src.sft_v3.qwen_distill

  # 3. After IEEE narratives are merged in, just rerun — already-completed
  #    (data_uuid, sample_idx) pairs are skipped.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.sft_v3.prompt_template import SYSTEM_PROMPT, build_user_prompt

# ── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_INPUT = Path("data/sft_v3/dataset_b_qwen_input.parquet")
DEFAULT_OUTPUT = Path("data/sft_v3/qwen_distilled.parquet")
DEFAULT_RAW_LOG = Path("data/sft_v3/qwen_raw_completions.jsonl")

DEFAULT_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507-tput"
DEFAULT_API_BASE = "https://api.together.xyz/v1"
DEFAULT_API_KEY_ENV = "TOGETHER_API_KEY"

DEFAULT_N_SAMPLES = 3
DEFAULT_MIN_AGREEMENT = 2  # of N samples
DEFAULT_CONCURRENCY = 8
DEFAULT_MAX_TOKENS = 1500
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TIMEOUT = 120  # seconds per request
DEFAULT_RETRIES = 3

VERDICT_RE = re.compile(r"verdict\s*[:\-]\s*([a-z_]+)", re.IGNORECASE)


# ── Data types ──────────────────────────────────────────────────────────────
@dataclass
class CompletionTask:
    data_uuid: str
    sample_idx: int
    prompt_user: str          # the user-turn content
    gt_is_fraud: int          # not sent to model; preserved for the filter step


@dataclass
class CompletionResult:
    data_uuid: str
    sample_idx: int
    completion: str | None
    verdict: str | None       # "fraud" | "not_fraud" | None (unparseable)
    error: str | None
    latency_s: float


# ── API ─────────────────────────────────────────────────────────────────────
def call_chat(api_base: str, api_key: str, model: str, system: str, user: str,
              max_tokens: int, temperature: float, timeout: int) -> str:
    """Single OpenAI-compatible chat completion call. Raises on HTTP error."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(f"{api_base}/chat/completions", json=payload,
                      headers=headers, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def call_chat_with_retry(api_base: str, api_key: str, model: str, system: str, user: str,
                         max_tokens: int, temperature: float, timeout: int,
                         retries: int) -> tuple[str | None, str | None]:
    """Returns (completion, error). Exponential backoff on transient errors."""
    delay = 2.0
    last_err = None
    for attempt in range(retries):
        try:
            return call_chat(api_base, api_key, model, system, user,
                             max_tokens, temperature, timeout), None
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            body = e.response.text[:400] if e.response is not None else ""
            last_err = f"HTTP {code}: {body}"
            if code in (429, 500, 502, 503, 504):
                time.sleep(delay); delay *= 2
                continue
            return None, last_err  # 4xx other than 429 — don't retry
        except (requests.ConnectionError, requests.Timeout) as e:
            last_err = f"{type(e).__name__}: {str(e)[:120]}"
            time.sleep(delay); delay *= 2
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:120]}"
    return None, last_err or "exhausted retries"


# ── Verdict parsing ─────────────────────────────────────────────────────────
def parse_verdict(completion: str | None) -> str | None:
    if not completion:
        return None
    m = VERDICT_RE.search(completion)
    if not m:
        return None
    v = m.group(1).strip().lower()
    if "not" in v or v in ("legit", "legitimate", "negative"):
        return "not_fraud"
    if v in ("fraud", "fraudulent", "positive"):
        return "fraud"
    return None


# ── Resumable log ───────────────────────────────────────────────────────────
def load_completed_pairs(log_path: Path) -> set[tuple[str, int]]:
    """Read the raw JSONL to discover which (data_uuid, sample_idx) pairs are done."""
    if not log_path.exists():
        return set()
    done = set()
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("completion") is not None:
                    done.add((rec["data_uuid"], rec["sample_idx"]))
            except Exception:
                continue
    return done


def append_log(log_path: Path, result: CompletionResult) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "data_uuid": result.data_uuid,
            "sample_idx": result.sample_idx,
            "completion": result.completion,
            "verdict": result.verdict,
            "error": result.error,
            "latency_s": round(result.latency_s, 3),
        }, ensure_ascii=False) + "\n")


# ── Build tasks ─────────────────────────────────────────────────────────────
def build_tasks(df: pd.DataFrame, n_samples: int, completed: set[tuple[str, int]]
                ) -> list[CompletionTask]:
    tasks: list[CompletionTask] = []
    for r in df.to_dict(orient="records"):
        uid = r["data_uuid"]
        prompt = build_user_prompt(r)
        gt = int(r.get("_gt_is_fraud", 0))
        for i in range(n_samples):
            if (uid, i) in completed:
                continue
            tasks.append(CompletionTask(data_uuid=uid, sample_idx=i,
                                        prompt_user=prompt, gt_is_fraud=gt))
    return tasks


# ── Aggregate + filter ──────────────────────────────────────────────────────
def aggregate(df_in: pd.DataFrame, log_path: Path,
              min_agreement: int, n_samples: int) -> pd.DataFrame:
    # Load all completions for the data_uuids in df_in
    uids = set(df_in["data_uuid"].astype(str))
    by_uid: dict[str, list[dict]] = {}
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec["data_uuid"] in uids and rec.get("completion") is not None:
                by_uid.setdefault(rec["data_uuid"], []).append(rec)

    rows = []
    stats = Counter()
    for r in df_in.to_dict(orient="records"):
        uid = r["data_uuid"]
        comps = by_uid.get(uid, [])
        if len(comps) < n_samples:
            stats["incomplete"] += 1
            continue
        verdicts = [c.get("verdict") for c in comps if c.get("verdict")]
        if not verdicts:
            stats["unparseable"] += 1
            continue
        v_counts = Counter(verdicts)
        top, top_n = v_counts.most_common(1)[0]
        if top_n < min_agreement:
            stats["low_agreement"] += 1
            continue
        gt = int(r.get("_gt_is_fraud", 0))
        gt_label = "fraud" if gt == 1 else "not_fraud"
        if top != gt_label:
            stats["disagreed_with_gt"] += 1
            continue
        # Pick the CoT from the first completion that matches the modal verdict
        cot = next(c["completion"] for c in comps if c.get("verdict") == top)
        rows.append({
            "data_uuid": uid,
            "archetype": r.get("archetype"),
            "narrative_text": r.get("narrative_text"),
            "fraud_vector_hint": r.get("fraud_vector_hint"),
            "language": r.get("language"),
            "instrument": r.get("instrument"),
            "_gt_is_fraud": gt,
            "qwen_verdict": top,
            "qwen_self_consistency": top_n,
            "qwen_cot": cot,
            "_source": r.get("_source"),
            "prompt": f"{SYSTEM_PROMPT}\n\n{build_user_prompt(r)}",
            "completion": cot,
        })
        stats["passed"] += 1

    print("\n[aggregate] stats:")
    for k, v in stats.items():
        print(f"  {k:24s}: {v}")
    print(f"  TOTAL kept                : {len(rows)}  /  {len(df_in)}")
    return pd.DataFrame(rows)


# ── Main ────────────────────────────────────────────────────────────────────
def main(args: argparse.Namespace) -> None:
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"ERROR: {args.api_key_env} not set in environment.")
        sys.exit(1)

    df = pd.read_parquet(args.input)
    if args.smoke_test:
        df = df.head(10)
        args.n_samples = 2
        args.min_agreement = 2
        print(f"[smoke-test] using {len(df)} rows, n_samples=2, min_agreement=2")
    elif args.limit:
        df = df.head(args.limit)
        print(f"[limit] using {len(df)} rows")

    print(f"[input] {args.input}: {len(df)} rows")
    print(f"[model] {args.model}  via  {args.api_base}")

    completed = load_completed_pairs(args.raw_log)
    if completed:
        print(f"[resume] {len(completed)} (uuid, sample) pairs already in log")

    tasks = build_tasks(df, args.n_samples, completed)
    print(f"[plan] {len(tasks)} API calls to make "
          f"(n_samples={args.n_samples}, concurrency={args.concurrency})")
    if not tasks:
        print("[plan] nothing to do — all (uuid, sample) pairs already in log")
    else:
        run_calls(tasks, args, api_key)

    if not args.output:
        print("[skip] no --output; aggregation skipped")
        return
    print(f"\n[aggregate] writing filtered SFT parquet -> {args.output}")
    out_df = aggregate(df, args.raw_log, args.min_agreement, args.n_samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(args.output, index=False)
    print(f"[write] {args.output}: {len(out_df)} rows")
    if len(out_df):
        print(f"[stats] archetype: {out_df['archetype'].value_counts().to_dict()}")
        print(f"[stats] qwen_verdict: {out_df['qwen_verdict'].value_counts().to_dict()}")


def run_calls(tasks: list[CompletionTask], args: argparse.Namespace, api_key: str) -> None:
    t_start = time.time()
    done_count = 0
    err_count = 0

    def one(task: CompletionTask) -> CompletionResult:
        t0 = time.time()
        completion, err = call_chat_with_retry(
            api_base=args.api_base,
            api_key=api_key,
            model=args.model,
            system=SYSTEM_PROMPT,
            user=task.prompt_user,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            timeout=args.timeout,
            retries=args.retries,
        )
        verdict = parse_verdict(completion)
        return CompletionResult(
            data_uuid=task.data_uuid,
            sample_idx=task.sample_idx,
            completion=completion,
            verdict=verdict,
            error=err,
            latency_s=time.time() - t0,
        )

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(one, t) for t in tasks]
        for fut in as_completed(futures):
            res = fut.result()
            append_log(args.raw_log, res)
            done_count += 1
            if res.error or not res.completion:
                err_count += 1
            if done_count % 25 == 0 or done_count == len(tasks):
                elapsed = time.time() - t_start
                rate = done_count / elapsed if elapsed > 0 else 0
                eta = (len(tasks) - done_count) / rate if rate > 0 else 0
                print(f"  [{done_count}/{len(tasks)}]  errs={err_count}  "
                      f"rate={rate:.2f}/s  eta={eta/60:.1f}min")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--raw-log", type=Path, default=DEFAULT_RAW_LOG)
    p.add_argument("--model", type=str, default=DEFAULT_MODEL)
    p.add_argument("--api-base", type=str, default=DEFAULT_API_BASE)
    p.add_argument("--api-key-env", type=str, default=DEFAULT_API_KEY_ENV)
    p.add_argument("--n-samples", type=int, default=DEFAULT_N_SAMPLES)
    p.add_argument("--min-agreement", type=int, default=DEFAULT_MIN_AGREEMENT)
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    p.add_argument("--limit", type=int, default=None,
                   help="Process only first N rows from input (testing)")
    p.add_argument("--smoke-test", action="store_true",
                   help="Override: 10 rows, n_samples=2; for end-to-end validation")
    return p


if __name__ == "__main__":
    main(build_parser().parse_args())