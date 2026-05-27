"""Pass 2 (judge-style CoT) generation via Adaption Labs for the v3 SFT corpus.

For each fraud row, we send a JUDGE prompt (the same template Gemma will train
on, from prompt_template.py) to Adaption Labs with reasoning_traces enabled.
Adaption returns judge-format CoT in the same style as v4 cot_dataset.parquet,
which keeps the Dataset A and Dataset B supervision stylistically consistent.

Sources (deduped by data_uuid):
  - data/sft_v3/dataset_b_qwen_input.parquet                          (v3+v4+HF)
  - datasets/ieee_for_adaption/{archetype}/transactions_ieee_adapted.parquet

Default: --fraud-only is True. Dataset A's 1,963 non-fraud CoT rows already
cover the legitimate-transaction supervision, so we don't pay to regenerate
non-fraud CoT.

Subcommands:
  --estimate    Upload + estimate credits per archetype
  --submit      Upload + submit Pass 2 runs (fire-and-forget)
  --check       Poll job statuses
  --download    Pull adapted JSONLs, build data/sft_v3/pass2_cot.parquet

Run:
  python -m src.sft_v3.adaption_pass2_v3 --estimate
  python -m src.sft_v3.adaption_pass2_v3 --submit
  python -m src.sft_v3.adaption_pass2_v3 --check
  python -m src.sft_v3.adaption_pass2_v3 --download
"""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from adaption import Adaption

from src.sft_v3.prompt_template import SYSTEM_PROMPT, build_user_prompt

ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
DATASET_B = Path("data/sft_v3/dataset_b_qwen_input.parquet")
IEEE_DIR = Path("datasets/ieee_for_adaption")

PASS2_DIR = Path("datasets/sft_v3_pass2")
# Default (fraud) paths — overridden when --non-fraud-only is set
TRACKER_PATH = PASS2_DIR / "adaption_jobs.json"
OUTPUT_PARQUET = Path("data/sft_v3/pass2_cot.parquet")
JSONL_NAME = "for_pass2.jsonl"

# Non-fraud scope paths (separate so a parallel non-fraud run doesn't clobber fraud)
TRACKER_PATH_NF = PASS2_DIR / "adaption_jobs_nonfraud.json"
OUTPUT_PARQUET_NF = Path("data/sft_v3/pass2_cot_nonfraud.parquet")
JSONL_NAME_NF = "for_pass2_nonfraud.jsonl"

COLUMN_MAPPING = {
    "prompt": "prompt",
    "completion": "completion",
    "context": ["archetype", "fraud_vector", "language", "instrument",
                "amount_usd", "is_fraud", "data_uuid"],
}
# Recipe mirrors the one that produced v4 cot_dataset.parquet (judge-style CoT)
RECIPE_SPEC = {
    "version": "v1",
    "recipes": {
        "deduplication": False,
        "prompt_rephrase": True,
        "reasoning_traces": True,
        "preference_pairs": False,
        "prompt_metadata_injection": True,
    },
}
BRAND_CONTROLS = {"length": "detailed", "hallucination_mitigation": False}


# ── Source assembly ─────────────────────────────────────────────────────────
def load_pool(fraud_only: bool, include_dataset_b: bool = True,
              non_fraud_only: bool = False) -> pd.DataFrame:
    """Combine Dataset B + IEEE-adapted, optionally filter by label class.

    - fraud_only=True keeps is_fraud==1 (default)
    - non_fraud_only=True keeps is_fraud==0 (overrides fraud_only)
    - include_dataset_b=False uses IEEE-adapted ONLY — used when running
      Adaption Pass 2 in parallel with the Qwen distillation pass to avoid
      re-doing CoT on the same Dataset B uuids.
    """
    frames: list[pd.DataFrame] = []

    if include_dataset_b and DATASET_B.exists():
        db = pd.read_parquet(DATASET_B)
        db["_source"] = db.get("_source", "dataset_b")
        # Standardize the column names Pass 2 needs
        db = db.rename(columns={
            "fraud_vector_hint": "fraud_vector",
            "_gt_is_fraud": "is_fraud",
        })
        db["amount_usd"] = db["transaction_amount_usd"]
        frames.append(db)
        print(f"[load] dataset_b: {len(db)} rows")
    elif not include_dataset_b:
        print("[load] dataset_b: SKIPPED (--ieee-only)")

    for a in ARCHETYPES:
        p = IEEE_DIR / a / "transactions_ieee_adapted.parquet"
        if not p.exists():
            print(f"[load] ieee {a}: missing ({p}) -- skipping")
            continue
        d = pd.read_parquet(p)
        d["_source"] = "ieee_adapted"
        # IEEE adapted parquet already has the right column names (is_fraud, amount_usd, etc.)
        frames.append(d)
        print(f"[load] ieee {a}: {len(d)} rows")

    if not frames:
        raise SystemExit("No input sources found.")
    pool = pd.concat(frames, ignore_index=True)
    pool = pool.drop_duplicates(subset=["data_uuid"])
    pool = pool[pool["narrative_text"].notna() & (pool["narrative_text"].astype(str).str.len() > 50)]
    if non_fraud_only:
        before = len(pool)
        pool = pool[pool["is_fraud"] == 0]
        print(f"[filter] non-fraud-only: {before} -> {len(pool)}")
    elif fraud_only:
        before = len(pool)
        pool = pool[pool["is_fraud"] == 1]
        print(f"[filter] fraud-only: {before} -> {len(pool)}")
    return pool.reset_index(drop=True)


def build_for_adaption_row(r: dict) -> dict:
    """Wrap one row as an Adaption Pass-2 input record.

    Prompt = the same judge instruction Gemma will see at inference.
    Completion = "" (Adaption fills this with judge-format CoT).
    """
    user_prompt = build_user_prompt(r)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
    return {
        "prompt": full_prompt,
        "completion": "",
        "data_uuid": r["data_uuid"],
        "archetype": r["archetype"],
        "fraud_vector": str(r.get("fraud_vector", "unknown")),
        "language": str(r.get("language", "en")),
        "instrument": str(r.get("instrument", "unknown")),
        "amount_usd": float(r.get("amount_usd") or 0.0),
        "is_fraud": int(r.get("is_fraud", 0)),
    }


def write_per_archetype_jsonl(pool: pd.DataFrame, jsonl_name: str) -> dict[str, Path]:
    """Group by archetype, write one jsonl per archetype using the given filename."""
    out_paths: dict[str, Path] = {}
    for a in ARCHETYPES:
        sub = pool[pool["archetype"] == a]
        if sub.empty:
            print(f"[write] {a}: 0 rows -- skipping")
            continue
        sub_dir = PASS2_DIR / a
        sub_dir.mkdir(parents=True, exist_ok=True)
        path = sub_dir / jsonl_name
        with open(path, "w", encoding="utf-8") as f:
            for r in sub.to_dict(orient="records"):
                f.write(json.dumps(build_for_adaption_row(r), ensure_ascii=False) + "\n")
        print(f"[write] {a:11s}  {len(sub):5d}  -> {path}")
        out_paths[a] = path
    return out_paths


# ── Adaption operations ────────────────────────────────────────────────────
def _client() -> Adaption | None:
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return None
    return Adaption(api_key=api_key)


def _read_tracker(path: Path = TRACKER_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _write_tracker(tracker: dict, path: Path = TRACKER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tracker, indent=2))


def _upload_and_run(client: Adaption, paths: dict[str, Path], estimate: bool,
                    tracker_path: Path = TRACKER_PATH) -> dict:
    tracker = _read_tracker(tracker_path)
    for arch, path in paths.items():
        n_rows = sum(1 for _ in open(path, encoding="utf-8"))
        print(f"\n--- {arch.upper()} ({n_rows} rows) ---")

        if arch in tracker and "dataset_id" in tracker[arch]:
            dataset_id = tracker[arch]["dataset_id"]
            print(f"  [reuse] dataset_id from tracker: {dataset_id}")
        else:
            print(f"  [upload] {path}")
            up = client.datasets.upload_file(
                path=str(path), name=f"v3-pass2-{arch}-{n_rows}rows"
            )
            dataset_id = up.dataset_id
            print(f"  [upload] dataset_id = {dataset_id}")

        try:
            resp = client.datasets.run(
                dataset_id=dataset_id,
                column_mapping=COLUMN_MAPPING,
                recipe_specification=RECIPE_SPEC,
                brand_controls=BRAND_CONTROLS,
                estimate=estimate,
            )
            mode = "ESTIMATE" if estimate else "RUN"
            print(f"  [{mode}] credits={resp.estimated_credits_consumed} "
                  f"est_minutes={resp.estimated_minutes}")
            if not estimate:
                print(f"  [run] run_id = {resp.run_id}")

            tracker[arch] = {
                "dataset_id": dataset_id,
                "upload_path": str(path),
                "rows": n_rows,
                "estimated_credits": resp.estimated_credits_consumed,
                "estimated_minutes": resp.estimated_minutes,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "status": "estimated" if estimate else "running",
            }
            if not estimate:
                tracker[arch]["run_id"] = resp.run_id
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            continue

    _write_tracker(tracker, tracker_path)
    total = sum(t.get("estimated_credits", 0) for t in tracker.values())
    print(f"\n[tracker] {tracker_path}")
    print(f"[total]   estimated credits across archetypes: {total}")
    return tracker


def cmd_estimate_or_submit(estimate: bool, fraud_only: bool,
                           include_dataset_b: bool = True,
                           non_fraud_only: bool = False) -> None:
    client = _client()
    if client is None:
        return
    pool = load_pool(fraud_only=fraud_only, include_dataset_b=include_dataset_b,
                     non_fraud_only=non_fraud_only)
    print(f"[pool] {len(pool)} rows for Pass 2")
    if pool.empty:
        return
    jsonl_name = JSONL_NAME_NF if non_fraud_only else JSONL_NAME
    tracker_path = TRACKER_PATH_NF if non_fraud_only else TRACKER_PATH
    paths = write_per_archetype_jsonl(pool, jsonl_name)
    if not paths:
        return
    _upload_and_run(client, paths, estimate=estimate, tracker_path=tracker_path)


def cmd_check(non_fraud_only: bool = False) -> None:
    client = _client()
    if client is None:
        return
    tracker_path = TRACKER_PATH_NF if non_fraud_only else TRACKER_PATH
    tracker = _read_tracker(tracker_path)
    if not tracker:
        print(f"No tracker at {tracker_path}. Run --submit first.")
        return
    print(f"{'Archetype':<13} {'Status':<12} {'Progress':<20} {'Dataset ID'}")
    print("-" * 70)
    all_done = True
    for arch, info in tracker.items():
        try:
            s = client.datasets.get_status(info["dataset_id"])
            progress = ""
            if s.progress:
                p = s.progress
                progress = f"{p.processed_rows}/{p.total_rows}"
                if p.percent:
                    progress += f" ({p.percent:.0f}%)"
            print(f"  {arch:<11} {s.status:<12} {progress:<20} {info['dataset_id'][:16]}...")
            tracker[arch]["status"] = s.status
            if s.status not in ("succeeded", "failed"):
                all_done = False
        except Exception as e:
            print(f"  {arch:<11} error: {str(e)[:60]}")
            all_done = False
    _write_tracker(tracker, tracker_path)
    if all_done:
        suffix = " --non-fraud-only" if non_fraud_only else ""
        print(f"\nAll done. Run: python -m src.sft_v3.adaption_pass2_v3 --download{suffix}")
    else:
        print("\nStill running.")


def cmd_download(non_fraud_only: bool = False) -> None:
    client = _client()
    if client is None:
        return
    tracker_path = TRACKER_PATH_NF if non_fraud_only else TRACKER_PATH
    output_parquet = OUTPUT_PARQUET_NF if non_fraud_only else OUTPUT_PARQUET
    tracker = _read_tracker(tracker_path)
    if not tracker:
        print(f"No tracker at {tracker_path}")
        return

    all_records: list[dict] = []
    for arch, info in tracker.items():
        print(f"\n--- {arch.upper()} ---")
        st = client.datasets.get_status(info["dataset_id"])
        if st.status != "succeeded":
            print(f"  status={st.status} -- skipping")
            continue
        try:
            ev = client.datasets.get_evaluation(info["dataset_id"])
            if ev.quality:
                q = ev.quality
                print(f"  quality: {q.grade_before} ({q.score_before}) -> "
                      f"{q.grade_after} ({q.score_after})  +{q.improvement_percent}%")
        except Exception:
            pass

        result = client.datasets.download(info["dataset_id"], file_format="jsonl")
        sub = PASS2_DIR / arch
        raw_name = "pass2_output_nonfraud.jsonl" if non_fraud_only else "pass2_output.jsonl"
        raw_path = sub / raw_name
        raw_path.write_text(result, encoding="utf-8")
        recs = [json.loads(line) for line in result.strip().split("\n") if line.strip()]
        for r in recs:
            r["_archetype"] = arch
        all_records.extend(recs)
        print(f"  records: {len(recs)}  ->  {raw_path}")
        tracker[arch]["status"] = "downloaded"
        tracker[arch]["adapted_records"] = len(recs)

    _write_tracker(tracker, tracker_path)

    if not all_records:
        print("\nNo successful downloads; not writing parquet.")
        return

    df = pd.DataFrame(all_records)
    # Adaption returns the CoT in `enhanced_completion`; reasoning_trace as
    # `reasoning_trace`. Mirror v4 cot_dataset column names where we can.
    cot_col = "enhanced_completion" if "enhanced_completion" in df.columns else "completion"
    reasoning_col = "reasoning_trace" if "reasoning_trace" in df.columns else None
    keep = [c for c in [
        "data_uuid", "_archetype", "fraud_vector", "language", "instrument",
        "amount_usd", "is_fraud", "prompt", "enhanced_prompt",
        cot_col, reasoning_col,
    ] if c is not None and c in df.columns]
    df = df[keep].rename(columns={
        "_archetype": "archetype",
        cot_col: "cot_completion",
        **({reasoning_col: "cot_reasoning_trace"} if reasoning_col else {}),
    })

    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_parquet, index=False)
    print(f"\n[write] {output_parquet}: {len(df)} rows")
    print(f"[stats] archetype: {df['archetype'].value_counts().to_dict()}")
    if "is_fraud" in df.columns:
        print(f"[stats] is_fraud:  {df['is_fraud'].value_counts().to_dict()}")
    print(f"[stats] avg cot_completion chars: {df['cot_completion'].astype(str).str.len().mean():.0f}")


# ── CLI ─────────────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--estimate", action="store_true")
    g.add_argument("--submit", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--download", action="store_true")
    p.add_argument("--all-rows", action="store_true",
                   help="Include non-fraud too (default is fraud-only)")
    p.add_argument("--ieee-only", action="store_true",
                   help="Skip Dataset B; use only IEEE-adapted rows. Avoids "
                        "overlap with a parallel Qwen distillation run.")
    p.add_argument("--non-fraud-only", action="store_true",
                   help="Run Pass 2 on non-fraud rows only. Uses a separate "
                        "tracker (adaption_jobs_nonfraud.json) and output "
                        "(pass2_cot_nonfraud.parquet) so it does not collide "
                        "with a parallel fraud-only run.")
    args = p.parse_args()

    fraud_only = not args.all_rows
    include_dataset_b = not args.ieee_only
    non_fraud_only = args.non_fraud_only
    if args.estimate:
        cmd_estimate_or_submit(estimate=True, fraud_only=fraud_only,
                               include_dataset_b=include_dataset_b,
                               non_fraud_only=non_fraud_only)
    elif args.submit:
        cmd_estimate_or_submit(estimate=False, fraud_only=fraud_only,
                               include_dataset_b=include_dataset_b,
                               non_fraud_only=non_fraud_only)
    elif args.check:
        cmd_check(non_fraud_only=non_fraud_only)
    elif args.download:
        cmd_download(non_fraud_only=non_fraud_only)


if __name__ == "__main__":
    main()