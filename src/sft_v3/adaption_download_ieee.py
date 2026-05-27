"""Download completed IEEE Adaption Labs results.

Saves the raw adapted JSONL per archetype, and writes a merged
parquet (transactions_ieee_adapted.parquet) that lives next to the input
for_adaption.jsonl files. Does NOT touch the v1/v4 archetype folders.

Usage:
    python -m src.sft_v3.adaption_download_ieee
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import pandas as pd
from adaption import Adaption

TRACKER_PATH = Path("datasets/ieee_for_adaption/adaption_jobs.json")
OUT_DIR = Path("datasets/ieee_for_adaption")


def download_all() -> None:
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return
    if not TRACKER_PATH.exists():
        print(f"No tracker at {TRACKER_PATH}")
        return

    tracker = json.loads(TRACKER_PATH.read_text())
    client = Adaption(api_key=api_key)

    spec_df = pd.read_parquet(OUT_DIR / "spec.parquet") if (OUT_DIR / "spec.parquet").exists() else None

    for arch, info in tracker.items():
        dataset_id = info["dataset_id"]
        print(f"\n--- {arch.upper()} ---")
        status = client.datasets.get_status(dataset_id)
        if status.status != "succeeded":
            print(f"  status={status.status}, skipping")
            continue

        try:
            ev = client.datasets.get_evaluation(dataset_id)
            if ev.quality:
                q = ev.quality
                print(f"  quality: {q.grade_before} ({q.score_before}) -> {q.grade_after} ({q.score_after})  +{q.improvement_percent}%")
        except Exception:
            pass

        print("  downloading...")
        result = client.datasets.download(dataset_id, file_format="jsonl")
        sub = OUT_DIR / arch
        sub.mkdir(parents=True, exist_ok=True)
        raw_path = sub / "adapted_output.jsonl"
        raw_path.write_text(result, encoding="utf-8")

        records = [json.loads(line) for line in result.strip().split("\n") if line.strip()]
        print(f"  records: {len(records)}  ->  {raw_path}")

        # Build a tidy parquet keyed on data_uuid; join in IEEE spec sidecar if present
        df = pd.DataFrame(records)
        narrative_col = "enhanced_completion" if "enhanced_completion" in df.columns else "completion"
        keep_cols = [c for c in [
            "data_uuid", "archetype", "fraud_vector", "language", "instrument",
            "amount_usd", "is_fraud", "prompt", "enhanced_prompt", narrative_col,
        ] if c in df.columns]
        df = df[keep_cols].rename(columns={narrative_col: "narrative_text"})

        if spec_df is not None:
            arch_spec = spec_df[spec_df["archetype"] == arch][[
                "data_uuid", "sender_age", "_ieee_transaction_id",
                "_ieee_product_cd", "_ieee_p_emaildomain", "_ieee_card6",
            ]]
            df = df.merge(arch_spec, on="data_uuid", how="left")

        out_parquet = sub / "transactions_ieee_adapted.parquet"
        df.to_parquet(out_parquet, index=False)
        print(f"  parquet: {out_parquet}  ({len(df)} rows)")

        tracker[arch]["status"] = "downloaded"
        tracker[arch]["adapted_records"] = len(records)
        tracker[arch]["parquet"] = str(out_parquet)

    TRACKER_PATH.write_text(json.dumps(tracker, indent=2))
    print(f"\n[tracker] updated: {TRACKER_PATH}")
    print("\nNext: extend Dataset B with these narratives + run Qwen distillation.")


if __name__ == "__main__":
    download_all()