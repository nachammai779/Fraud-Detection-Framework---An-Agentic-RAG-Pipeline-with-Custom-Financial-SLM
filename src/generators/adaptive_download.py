"""
adaptive_download.py
====================
Downloads completed adaptation results, merges narratives back
into the TabDDPM parquets, and runs language verification.

Usage:
    python adaptive_download.py
"""

import os
import sys
import json
import pandas as pd

from adaption import Adaption

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRACKER_PATH = os.path.join(PROJECT_ROOT, "datasets", "adaption_jobs.json")


def find_parquet(archetype):
    candidates = [
        os.path.join(PROJECT_ROOT, "notebooks", "generation", "tabddpm_output", archetype, "transactions.parquet"),
        os.path.join(PROJECT_ROOT, "datasets", archetype, "synthetic", "transactions.parquet"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def download_all():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return

    if not os.path.exists(TRACKER_PATH):
        print(f"No tracker found at {TRACKER_PATH}")
        return

    with open(TRACKER_PATH, "r") as f:
        tracker = json.load(f)

    client = Adaption(api_key=api_key)

    for arch, info in tracker.items():
        dataset_id = info["dataset_id"]
        print(f"\n{'='*60}")
        print(f"  {arch.upper()}")
        print(f"{'='*60}")

        # Check status
        status = client.datasets.get_status(dataset_id)
        if status.status != "succeeded":
            print(f"  Status: {status.status} -- skipping (not done yet)")
            continue

        # Get evaluation
        try:
            ev = client.datasets.get_evaluation(dataset_id)
            if ev.quality:
                print(f"  Quality: {ev.quality.grade_before} ({ev.quality.score_before}) -> {ev.quality.grade_after} ({ev.quality.score_after}) | +{ev.quality.improvement_percent}%")
        except Exception:
            pass

        # Download
        print(f"  Downloading...")
        result = client.datasets.download(dataset_id, file_format="jsonl")

        adaptive_dir = os.path.join(PROJECT_ROOT, "datasets", arch, "adaptive")
        os.makedirs(adaptive_dir, exist_ok=True)

        # Save raw output
        output_path = os.path.join(adaptive_dir, "adapted_output.jsonl")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)

        records = [json.loads(line) for line in result.strip().split("\n") if line.strip()]
        print(f"  Downloaded: {len(records)} records")

        # Save prompt reference
        ref_path = os.path.join(adaptive_dir, "prompt_reference.csv")
        ref_rows = []
        for r in records:
            ref_rows.append({
                "data_uuid": r.get("data_uuid", ""),
                "fraud_vector": r.get("fraud_vector", ""),
                "language": r.get("language", ""),
                "instrument": r.get("instrument", ""),
                "is_fraud": r.get("is_fraud", ""),
                "prompt": r.get("prompt", ""),
                "enhanced_prompt": r.get("enhanced_prompt", ""),
            })
        pd.DataFrame(ref_rows).to_csv(ref_path, index=False)
        print(f"  Prompt reference: {ref_path}")

        # Merge into parquet
        parquet_path = find_parquet(arch)
        if parquet_path:
            print(f"  Merging into: {parquet_path}")
            df = pd.read_parquet(parquet_path)

            narrative_col = "enhanced_completion" if "enhanced_completion" in records[0] else "completion"
            narrative_map = {r["data_uuid"]: r[narrative_col] for r in records if r.get(narrative_col)}

            filled = 0
            for idx, row in df.iterrows():
                uid = row.get("data_uuid", "")
                if uid in narrative_map and narrative_map[uid]:
                    df.at[idx, "narrative_text"] = str(narrative_map[uid])[:2000]
                    filled += 1

            print(f"  Filled: {filled}/{len(df)} narrative_text fields")

            # Save
            out_parquet = os.path.join(adaptive_dir, "transactions_adapted.parquet")
            out_csv = os.path.join(adaptive_dir, f"transactions_adapted_{arch}.csv")
            df.to_parquet(out_parquet, index=False, engine="pyarrow")
            df.to_csv(out_csv, index=False)
            print(f"  Parquet: {out_parquet}")
            print(f"  CSV:     {out_csv}")

            # Update tracker
            tracker[arch]["status"] = "downloaded"
            tracker[arch]["adapted_records"] = len(records)
            tracker[arch]["filled_narratives"] = filled
        else:
            print(f"  WARNING: No parquet found for {arch}, raw output saved only")

    # Save updated tracker
    with open(TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2)

    print(f"\n{'='*60}")
    print("DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    for arch, info in tracker.items():
        status = info.get("status", "unknown")
        adapted = info.get("adapted_records", "?")
        filled = info.get("filled_narratives", "?")
        print(f"  {arch}: status={status}, adapted={adapted}, filled={filled}")


if __name__ == "__main__":
    download_all()
