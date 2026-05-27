"""Assemble the final v3 SFT corpus from all teacher outputs.

Sources (all already in judge-prompt format — same SYSTEM + user-turn shape):
  - data/sft_v3/dataset_a_cot.parquet            (v4 CoT, Adaption Labs)
  - data/sft_v3/qwen_distilled.parquet           (Qwen3-235B distillation)
  - data/sft_v3/pass2_cot.parquet                (Adaption Pass 2, IEEE fraud)
  - data/sft_v3/pass2_cot_nonfraud.parquet       (Adaption Pass 2, IEEE non-fraud)

Output:
  - data/sft_v3/sft_corpus_train.parquet
  - data/sft_v3/sft_corpus_eval.parquet

Stratified train/eval split (default 90/10) on (archetype, is_fraud, _source) so
all combinations land in both splits. Final per-row schema:
  data_uuid, archetype, is_fraud, language, fraud_vector, _source,
  prompt, completion, messages

Run:
  python -m src.sft_v3.assemble_sft_corpus
  python -m src.sft_v3.assemble_sft_corpus --eval-frac 0.1 --seed 42
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import pandas as pd

from src.sft_v3.prompt_template import SYSTEM_PROMPT

DEFAULT_OUT_DIR = Path("data/sft_v3")
DEFAULT_TRAIN = DEFAULT_OUT_DIR / "sft_corpus_train.parquet"
DEFAULT_EVAL = DEFAULT_OUT_DIR / "sft_corpus_eval.parquet"

SOURCES = {
    "v4_cot":               Path("data/sft_v3/dataset_a_cot.parquet"),
    "qwen_distilled":       Path("data/sft_v3/qwen_distilled.parquet"),
    "adaption_pass2_fraud": Path("data/sft_v3/pass2_cot.parquet"),
    "adaption_pass2_nf":    Path("data/sft_v3/pass2_cot_nonfraud.parquet"),
}

UNIFIED_COLS = ["data_uuid", "archetype", "is_fraud", "language",
                "fraud_vector", "_source", "prompt", "completion", "messages"]


def _build_messages(prompt: str, completion: str) -> str:
    """Re-derive {system, user, assistant} messages from the flat prompt + completion.
    Stored as a JSON string so the parquet stays scalar-typed."""
    # All sources prepend SYSTEM_PROMPT followed by "\n\n" then the user turn.
    if prompt.startswith(SYSTEM_PROMPT):
        user_turn = prompt[len(SYSTEM_PROMPT):].lstrip("\n")
    else:
        user_turn = prompt
    return json.dumps([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_turn},
        {"role": "assistant", "content": completion},
    ], ensure_ascii=False)


def normalize(df: pd.DataFrame, source_tag: str) -> pd.DataFrame:
    """Project each teacher's parquet onto the unified schema."""
    out = pd.DataFrame()
    out["data_uuid"] = df["data_uuid"].astype(str)
    out["archetype"] = df["archetype"]
    if "is_fraud" in df.columns:
        out["is_fraud"] = df["is_fraud"].astype(int)
    elif "_gt_is_fraud" in df.columns:
        out["is_fraud"] = df["_gt_is_fraud"].astype(int)
    else:
        raise KeyError(f"{source_tag}: no is_fraud / _gt_is_fraud column")
    out["language"] = df.get("language")

    if "fraud_vector" in df.columns:
        out["fraud_vector"] = df["fraud_vector"]
    elif "fraud_vector_hint" in df.columns:
        out["fraud_vector"] = df["fraud_vector_hint"]
    else:
        out["fraud_vector"] = None

    out["_source"] = source_tag
    out["prompt"] = df["prompt"].astype(str)

    # Completion comes from different columns depending on the teacher
    if "completion" in df.columns and df["completion"].notna().any():
        completion = df["completion"]
    elif "cot_completion" in df.columns:
        completion = df["cot_completion"]
    elif "qwen_cot" in df.columns:
        completion = df["qwen_cot"]
    else:
        raise KeyError(f"{source_tag}: no completion / cot_completion / qwen_cot")
    out["completion"] = completion.astype(str)

    out["messages"] = [_build_messages(p, c) for p, c in zip(out["prompt"], out["completion"])]
    return out[UNIFIED_COLS]


def stratified_split(df: pd.DataFrame, eval_frac: float, seed: int
                     ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stratify by (archetype, is_fraud, _source). Each cell gets eval_frac to eval."""
    eval_parts: list[pd.DataFrame] = []
    train_parts: list[pd.DataFrame] = []
    for key, grp in df.groupby(["archetype", "is_fraud", "_source"], dropna=False):
        n = len(grp)
        n_eval = max(1, int(round(n * eval_frac))) if n >= 5 else 0
        shuf = grp.sample(frac=1.0, random_state=seed)
        eval_parts.append(shuf.iloc[:n_eval])
        train_parts.append(shuf.iloc[n_eval:])
    train_df = pd.concat(train_parts, ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    eval_df = pd.concat(eval_parts, ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return train_df, eval_df


def main(eval_frac: float, seed: int, out_train: Path, out_eval: Path) -> None:
    frames = []
    for tag, path in SOURCES.items():
        if not path.exists():
            print(f"[skip] {tag}: missing {path}")
            continue
        df = pd.read_parquet(path)
        nf = normalize(df, tag)
        # Drop empty/short completions defensively
        nf = nf[nf["completion"].str.len() > 200]
        print(f"[load] {tag:22s}  {len(df):5d} -> {len(nf):5d} after filter")
        frames.append(nf)

    if not frames:
        raise SystemExit("No source parquets found.")

    pool = pd.concat(frames, ignore_index=True)
    before = len(pool)
    pool = pool.drop_duplicates(subset=["data_uuid", "_source"])  # safety; should be no-ops
    print(f"[pool] {len(pool)} rows ({before - len(pool)} duplicate rows removed)")

    train_df, eval_df = stratified_split(pool, eval_frac=eval_frac, seed=seed)
    out_train.parent.mkdir(parents=True, exist_ok=True)
    train_df.to_parquet(out_train, index=False)
    eval_df.to_parquet(out_eval, index=False)

    print(f"\n[write] {out_train}: {len(train_df)} rows")
    print(f"[write] {out_eval}: {len(eval_df)} rows")

    print("\n[stats] train — _source x is_fraud:")
    print(train_df.groupby(["_source", "is_fraud"]).size().unstack(fill_value=0).to_string())
    print("\n[stats] train — archetype x is_fraud:")
    print(train_df.groupby(["archetype", "is_fraud"]).size().unstack(fill_value=0).to_string())
    print("\n[stats] eval  — _source x is_fraud:")
    print(eval_df.groupby(["_source", "is_fraud"]).size().unstack(fill_value=0).to_string())

    overall_fraud_rate = train_df["is_fraud"].mean()
    print(f"\n[stats] train overall fraud rate: {overall_fraud_rate:.1%}")
    print(f"[stats] train avg prompt chars:    {train_df['prompt'].str.len().mean():.0f}")
    print(f"[stats] train avg completion chars:{train_df['completion'].str.len().mean():.0f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--eval-frac", type=float, default=0.10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--train-out", type=Path, default=DEFAULT_TRAIN)
    p.add_argument("--eval-out", type=Path, default=DEFAULT_EVAL)
    args = p.parse_args()
    main(args.eval_frac, args.seed, args.train_out, args.eval_out)