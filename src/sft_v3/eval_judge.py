"""Evaluate the trained Gemma fraud judge on the held-out eval set.

Inputs:
    data/sft_v3/sft_corpus_eval.parquet     (2,214 held-out rows from the SFT corpus)
    data/sft_v3/gemma-judge-lora/            (LoRA adapter from train_lora.py)
    -- or --
    data/sft_v3/gemma-judge-merged/          (merged FP16, if you trained with --save-merged)

Outputs:
    data/sft_v3/eval_predictions.parquet     (per-row Gemma verdict + CoT)
    data/sft_v3/eval_report.json             (summary metrics)
    Console summary: overall, per-archetype, per-teacher-source breakdowns

Metrics computed:
    - Accuracy / precision / recall / F1 vs ground truth (is_fraud)
    - Per-archetype F1 (4 archetypes)
    - Per-source agreement: how often Gemma matches the teacher whose CoT
      was the training supervision for that row (v4_cot / qwen / adaption fraud / adaption nf)
    - Confusion matrix
    - Unparseable verdict count

Run on the same pod as training:
    python -m src.sft_v3.eval_judge --adapter-dir data/sft_v3/gemma-judge-lora
    python -m src.sft_v3.eval_judge --merged-dir data/sft_v3/gemma-judge-merged
"""
from __future__ import annotations
import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator

import pandas as pd
import torch

# Unsloth must be imported BEFORE transformers
from unsloth import FastLanguageModel  # type: ignore

from src.sft_v3.prompt_template import SYSTEM_PROMPT, build_user_prompt

EVAL_PARQUET = Path("data/sft_v3/sft_corpus_eval.parquet")
DEFAULT_ADAPTER = Path("data/sft_v3/gemma-judge-lora")
OUT_PREDICTIONS = Path("data/sft_v3/eval_predictions.parquet")
OUT_REPORT = Path("data/sft_v3/eval_report.json")

VERDICT_RE = re.compile(
    r"\**\s*verdict\s*\**\s*[:\-]?\s*\**\s*"
    r"(fraud|fraudulent|not[\s_]*fraud|not[\s_]*fraudulent|legitimate|legit|negative|positive)",
    re.IGNORECASE,
)


def parse_verdict(text: str | None) -> str | None:
    """Find the LAST verdict mention in the text — the model often paraphrases
    the verdict earlier (e.g., "Final Verdict: The transaction is fraudulent..."
    in prose) before stating the structured `verdict: fraud` near the end.

    Strict-regex-only by design: a prose fallback was tried and produced too
    many false negatives in v4_cot completions where "legitimate" appears
    inside analysis paragraphs (negated context). Unparseable rows are
    counted as abstentions, not misclassified."""
    if not text:
        return None
    matches = list(VERDICT_RE.finditer(text))
    if not matches:
        return None
    v = matches[-1].group(1).strip().lower().replace("_", " ").replace("  ", " ")
    if "not" in v or "legit" in v or v == "negative":
        return "not_fraud"
    return "fraud"


def batched(items: list, batch_size: int) -> Iterator[list]:
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def load_model(args: argparse.Namespace):
    if args.merged_dir:
        model_name = str(args.merged_dir)
        load_in_4bit = False
        print(f"[model] loading merged FP16 from {model_name}")
    else:
        model_name = str(args.adapter_dir)
        load_in_4bit = True
        print(f"[model] loading base + LoRA adapter from {model_name}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=load_in_4bit,
    )
    FastLanguageModel.for_inference(model)
    # Gemma4Processor expects multimodal content (list of typed parts) — we want
    # the text-only tokenizer. Unwrap if this is a processor.
    if hasattr(tokenizer, "tokenizer"):
        tokenizer = tokenizer.tokenizer
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    return model, tokenizer


def build_prompts(eval_df: pd.DataFrame, tokenizer) -> list[str]:
    prompts: list[str] = []
    for r in eval_df.to_dict(orient="records"):
        # Reconstruct the row dict prompt_template expects.
        # The eval corpus already has `prompt` ready, but we rebuild from raw
        # row data so the prompt is uniformly formatted from build_user_prompt.
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _extract_user_turn(r["prompt"])},
        ]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        prompts.append(text)
    return prompts


def _extract_user_turn(flat_prompt: str) -> str:
    """The stored `prompt` is SYSTEM_PROMPT + "\\n\\n" + user-turn. Strip the system part."""
    if flat_prompt.startswith(SYSTEM_PROMPT):
        return flat_prompt[len(SYSTEM_PROMPT):].lstrip("\n")
    return flat_prompt


def generate(model, tokenizer, prompts: list[str], batch_size: int,
             max_new_tokens: int) -> list[str]:
    """Batched left-padded generation. Tokenizer is unwrapped to the underlying
    text tokenizer in load_model, so processor-induced batching bugs are avoided."""
    out: list[str] = []
    t0 = time.time()
    n_total = len(prompts)
    n_done = 0
    for batch in batched(prompts, batch_size):
        enc = tokenizer(text=batch, return_tensors="pt", padding=True,
                        truncation=True, max_length=4096).to(model.device)
        with torch.no_grad():
            generated = model.generate(
                **enc,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=0.0,
                pad_token_id=tokenizer.pad_token_id,
            )
        # With left-padding, the input length is uniform across the batch
        input_len = enc["input_ids"].shape[1]
        for gen_ids in generated:
            new_ids = gen_ids[input_len:]
            out.append(tokenizer.decode(new_ids, skip_special_tokens=True))
        n_done += len(batch)
        elapsed = time.time() - t0
        rate = n_done / elapsed if elapsed > 0 else 0
        eta_min = (n_total - n_done) / rate / 60 if rate > 0 else 0
        print(f"  [{n_done}/{n_total}]  rate={rate:.2f}/s  eta={eta_min:.1f}min")
    return out


def compute_metrics(df: pd.DataFrame) -> dict:
    """All metrics derived from the predictions parquet."""
    res: dict = {}
    n = len(df)
    n_parseable = (df["gemma_verdict"].notna()).sum()
    n_unparseable = n - n_parseable
    res["n_total"] = int(n)
    res["n_unparseable"] = int(n_unparseable)
    res["parseable_pct"] = round(100 * n_parseable / n, 2) if n else 0

    sub = df.dropna(subset=["gemma_verdict"]).copy()
    sub["gemma_fraud"] = (sub["gemma_verdict"] == "fraud").astype(int)

    def f1(tp, fp, fn):
        prec = tp / (tp + fp) if (tp + fp) else 0
        rec = tp / (tp + fn) if (tp + fn) else 0
        f = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
        return round(prec, 4), round(rec, 4), round(f, 4)

    def block(d: pd.DataFrame) -> dict:
        if d.empty:
            return {"n": 0}
        tp = int(((d["gemma_fraud"] == 1) & (d["is_fraud"] == 1)).sum())
        fp = int(((d["gemma_fraud"] == 1) & (d["is_fraud"] == 0)).sum())
        tn = int(((d["gemma_fraud"] == 0) & (d["is_fraud"] == 0)).sum())
        fn = int(((d["gemma_fraud"] == 0) & (d["is_fraud"] == 1)).sum())
        p, r, f = f1(tp, fp, fn)
        return {"n": int(len(d)), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
                "accuracy": round((tp + tn) / len(d), 4),
                "precision": p, "recall": r, "f1": f}

    res["overall"] = block(sub)
    res["per_archetype"] = {a: block(sub[sub["archetype"] == a])
                            for a in sorted(sub["archetype"].unique())}
    res["per_source"] = {s: block(sub[sub["_source"] == s])
                         for s in sorted(sub["_source"].unique())}

    # Teacher-agreement: how often does Gemma agree with the teacher whose
    # CoT supervised that row? (Teacher verdict is parsed from `completion`.)
    sub["teacher_verdict"] = sub["completion"].apply(parse_verdict)
    sub_t = sub.dropna(subset=["teacher_verdict"])
    if len(sub_t):
        agree_overall = (sub_t["gemma_verdict"] == sub_t["teacher_verdict"]).mean()
        per_src_agree = {
            s: round((g["gemma_verdict"] == g["teacher_verdict"]).mean(), 4)
            for s, g in sub_t.groupby("_source")
        }
        res["teacher_agreement"] = {
            "n_with_teacher_verdict": int(len(sub_t)),
            "overall": round(float(agree_overall), 4),
            "per_source": per_src_agree,
        }
    else:
        res["teacher_agreement"] = {"n_with_teacher_verdict": 0}
    return res


def print_report(report: dict) -> None:
    def fmt_block(m: dict) -> str:
        if m.get("n", 0) == 0 or "accuracy" not in m:
            return f"n={m.get('n', 0):>4}  (no parseable verdicts)"
        return (f"n={m['n']:>4}  acc={m['accuracy']:.3f}  P={m['precision']:.3f}  "
                f"R={m['recall']:.3f}  F1={m['f1']:.3f}  "
                f"(TP/FP/TN/FN={m['tp']}/{m['fp']}/{m['tn']}/{m['fn']})")

    print("\n" + "=" * 70)
    print(f"OVERALL  {fmt_block(report['overall'])}")
    print(f"  unparseable verdicts: {report['n_unparseable']}/{report['n_total']} "
          f"({100 - report['parseable_pct']:.1f}%)")

    print("\nPER ARCHETYPE")
    for a, m in report["per_archetype"].items():
        print(f"  {a:12s} {fmt_block(m)}")

    print("\nPER SOURCE (the teacher whose CoT supervised that eval row)")
    for s, m in report["per_source"].items():
        print(f"  {s:22s} {fmt_block(m)}")

    ta = report.get("teacher_agreement", {})
    if ta.get("n_with_teacher_verdict"):
        print(f"\nTEACHER AGREEMENT  (Gemma verdict == teacher verdict on the same row)")
        print(f"  overall: {ta['overall']:.3f}  (n={ta['n_with_teacher_verdict']})")
        for s, v in ta["per_source"].items():
            print(f"    {s:22s}: {v:.3f}")
    print("=" * 70)


def main(args: argparse.Namespace) -> None:
    if not EVAL_PARQUET.exists():
        raise SystemExit(f"Missing {EVAL_PARQUET}. Run assemble_sft_corpus.py first.")
    if not args.adapter_dir.exists() and not (args.merged_dir and args.merged_dir.exists()):
        raise SystemExit("No adapter/merged dir found. Train first or pass --adapter-dir / --merged-dir.")

    eval_df = pd.read_parquet(EVAL_PARQUET)
    if args.limit:
        eval_df = eval_df.head(args.limit)
        print(f"[limit] using {len(eval_df)} rows")
    print(f"[data] eval rows: {len(eval_df)}")

    model, tokenizer = load_model(args)
    prompts = build_prompts(eval_df, tokenizer)

    print(f"[generate] batch_size={args.batch_size} max_new_tokens={args.max_new_tokens}")
    completions = generate(model, tokenizer, prompts,
                           batch_size=args.batch_size,
                           max_new_tokens=args.max_new_tokens)

    eval_df = eval_df.copy()
    eval_df["gemma_completion"] = completions
    eval_df["gemma_verdict"] = eval_df["gemma_completion"].apply(parse_verdict)
    eval_df["gemma_correct"] = (
        (eval_df["gemma_verdict"] == "fraud") == (eval_df["is_fraud"] == 1)
    )

    OUT_PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    keep = ["data_uuid", "archetype", "_source", "is_fraud",
            "completion", "gemma_completion", "gemma_verdict", "gemma_correct"]
    keep = [c for c in keep if c in eval_df.columns]
    eval_df[keep].to_parquet(OUT_PREDICTIONS, index=False)
    print(f"\n[write] predictions -> {OUT_PREDICTIONS}: {len(eval_df)} rows")

    report = compute_metrics(eval_df)
    OUT_REPORT.write_text(json.dumps(report, indent=2))
    print(f"[write] report -> {OUT_REPORT}")
    print_report(report)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--adapter-dir", type=Path, default=DEFAULT_ADAPTER,
                   help="LoRA adapter directory from train_lora.py")
    p.add_argument("--merged-dir", type=Path, default=None,
                   help="Optional: merged FP16 directory (skips LoRA loading)")
    p.add_argument("--max-seq-length", type=int, default=4096)
    p.add_argument("--max-new-tokens", type=int, default=1500)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--limit", type=int, default=None,
                   help="Cap eval to first N rows for a smoke run")
    return p.parse_args()


if __name__ == "__main__":
    main(parse_args())