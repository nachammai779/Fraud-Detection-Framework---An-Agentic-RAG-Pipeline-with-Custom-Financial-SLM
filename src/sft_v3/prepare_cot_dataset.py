"""Dataset A — v4 judge-style CoT in chat-template SFT format.

Reads: datasets_v4/reasoning/cot_dataset.parquet (3,926 rows)
Writes: data/sft_v3/dataset_a_cot.parquet

Each output row is one SFT example:
  - messages: [{role: system}, {role: user}, {role: assistant}]
  - prompt:   flat string (system + user) for non-chat trainers
  - completion: assistant turn (= v4 cot_completion)
  - data_uuid, archetype, is_fraud: passthrough for stratification / eval

Run: python -m src.sft_v3.prepare_cot_dataset
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import pandas as pd

from src.sft_v3.prompt_template import SYSTEM_PROMPT, build_user_prompt

DEFAULT_IN = Path("datasets_v4/reasoning/cot_dataset.parquet")
DEFAULT_OUT = Path("data/sft_v3/dataset_a_cot.parquet")


def main(in_path: Path, out_path: Path) -> None:
    df = pd.read_parquet(in_path)
    print(f"[load] {in_path}: {len(df)} rows, {len(df.columns)} cols")

    required = {"data_uuid", "archetype", "is_fraud", "cot_completion", "narrative_text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    out_rows = []
    skipped = 0
    for r in df.to_dict(orient="records"):
        completion = r.get("cot_completion")
        if not completion or not isinstance(completion, str):
            skipped += 1
            continue
        user_msg = build_user_prompt(r)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": completion},
        ]
        out_rows.append({
            "data_uuid": r["data_uuid"],
            "archetype": r["archetype"],
            "is_fraud": int(r["is_fraud"]),
            "fraud_vector_hint": r.get("fraud_vector_hint"),
            "language": r.get("language"),
            "messages": json.dumps(messages, ensure_ascii=False),
            "prompt": f"{SYSTEM_PROMPT}\n\n{user_msg}",
            "completion": completion,
            "_source": "v4_cot",
        })

    out_df = pd.DataFrame(out_rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)

    print(f"[write] {out_path}: {len(out_df)} rows  (skipped {skipped} empty-completion)")
    print(f"[stats] archetype: {out_df['archetype'].value_counts().to_dict()}")
    print(f"[stats] is_fraud:  {out_df['is_fraud'].value_counts().to_dict()}")
    print(f"[stats] avg prompt chars:     {out_df['prompt'].str.len().mean():.0f}")
    print(f"[stats] avg completion chars: {out_df['completion'].str.len().mean():.0f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", type=Path, default=DEFAULT_IN)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    main(args.input, args.output)