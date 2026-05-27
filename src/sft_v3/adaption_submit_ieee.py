"""Upload + submit IEEE-derived for_adaption.jsonl files to Adaption Labs.

Mirrors src/generators/adaptive_submit.py + adaptive_data.py but for the IEEE
inputs staged by prepare_ieee_for_adaption.py. Uses a separate tracker file
(datasets/ieee_for_adaption/adaption_jobs.json) so it does not collide with
the existing v1/v4 tracker.

Usage:
    # Set the key once in your shell:
    #   PowerShell:  $env:ADAPTION_API_KEY = "sk-..."
    #   Bash:        export ADAPTION_API_KEY=sk-...

    # Dry-run estimate first (free, no charge):
    python -m src.sft_v3.adaption_submit_ieee --estimate

    # Full submit (fire-and-forget):
    python -m src.sft_v3.adaption_submit_ieee

    # Then track:
    python -m src.sft_v3.adaption_check_ieee
    python -m src.sft_v3.adaption_download_ieee
"""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from adaption import Adaption

ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
INPUT_DIR = Path("datasets/ieee_for_adaption")
TRACKER_PATH = INPUT_DIR / "adaption_jobs.json"

COLUMN_MAPPING = {
    "prompt": "prompt",
    "completion": "completion",
    "context": ["archetype", "fraud_vector", "language", "instrument", "amount_usd", "is_fraud"],
}
RECIPE_SPEC = {
    "version": "v1",
    "recipes": {
        "deduplication": True,
        "prompt_rephrase": True,
        "reasoning_traces": False,
        "preference_pairs": False,
        "prompt_metadata_injection": True,
    },
}
BRAND_CONTROLS = {"length": "detailed", "hallucination_mitigation": False}


def submit_all(estimate: bool) -> None:
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set.")
        print("  PowerShell:  $env:ADAPTION_API_KEY = \"sk-...\"")
        print("  Bash:        export ADAPTION_API_KEY=sk-...")
        return

    client = Adaption(api_key=api_key)
    tracker: dict = {}
    if TRACKER_PATH.exists():
        tracker = json.loads(TRACKER_PATH.read_text())

    for arch in ARCHETYPES:
        upload_path = INPUT_DIR / arch / "for_adaption.jsonl"
        if not upload_path.exists():
            print(f"[skip] {arch}: missing {upload_path}")
            continue

        n_rows = sum(1 for _ in open(upload_path, encoding="utf-8"))
        print(f"\n--- {arch.upper()} ({n_rows} rows) ---")

        # Upload (or reuse if already in tracker)
        if arch in tracker and "dataset_id" in tracker[arch]:
            dataset_id = tracker[arch]["dataset_id"]
            print(f"  [reuse] dataset_id from tracker: {dataset_id}")
        else:
            print(f"  [upload] {upload_path}")
            up = client.datasets.upload_file(
                path=str(upload_path),
                name=f"fraud-ieee-{arch}-{n_rows}rows",
            )
            dataset_id = up.dataset_id
            print(f"  [upload] dataset_id = {dataset_id}")

        # Run
        try:
            resp = client.datasets.run(
                dataset_id=dataset_id,
                column_mapping=COLUMN_MAPPING,
                recipe_specification=RECIPE_SPEC,
                brand_controls=BRAND_CONTROLS,
                estimate=estimate,
            )
            mode = "ESTIMATE" if estimate else "RUN"
            print(f"  [{mode}] credits={resp.estimated_credits_consumed}  est_minutes={resp.estimated_minutes}")
            if not estimate:
                print(f"  [run] run_id = {resp.run_id}")

            tracker[arch] = {
                "dataset_id": dataset_id,
                "upload_path": str(upload_path),
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

    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_PATH.write_text(json.dumps(tracker, indent=2))
    print(f"\n[tracker] {TRACKER_PATH}")

    total_credits = sum(t.get("estimated_credits", 0) for t in tracker.values())
    print(f"[total]   estimated credits: {total_credits}")
    if estimate:
        print("\nNext: drop --estimate to actually submit.")
    else:
        print("\nNext: python -m src.sft_v3.adaption_check_ieee")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--estimate", action="store_true",
                   help="Dry-run to see credit estimate; no actual submission")
    args = p.parse_args()
    submit_all(estimate=args.estimate)