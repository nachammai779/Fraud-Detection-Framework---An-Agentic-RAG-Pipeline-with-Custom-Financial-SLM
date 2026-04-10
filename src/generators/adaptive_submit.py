"""
adaptive_submit.py
==================
Fire-and-forget: submits all 4 adaptation jobs without waiting.
Saves dataset IDs to a tracker file for later status check / download.

Usage:
    python adaptive_submit.py              # Submit all 4
    python adaptive_check.py               # Check status later
    python adaptive_download.py            # Download when done
"""

import os
import sys
import json
from datetime import datetime, timezone

from adaption import Adaption

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

TRACKER_PATH = os.path.join(PROJECT_ROOT, "datasets", "adaption_jobs.json")

# Dataset IDs from the estimate run (already uploaded)
DATASETS = {
    "remittance": "acb5a642-a867-48c0-a9fe-0c26854c0a1f",
    "gig_worker": "b294fe1d-1998-4a32-abd5-a9affd3a408f",
    "unbanked": "7fcd7144-a398-4c57-9c29-d861942d124d",
    "itin": "ab55da6a-7810-4b86-863c-a755019c139b",
}

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

BRAND_CONTROLS = {
    "length": "detailed",
    "hallucination_mitigation": False,
}


def submit_all():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return

    client = Adaption(api_key=api_key)
    tracker = {}

    for arch, dataset_id in DATASETS.items():
        print(f"\nSubmitting {arch.upper()} (dataset={dataset_id[:8]}...)...")
        try:
            resp = client.datasets.run(
                dataset_id=dataset_id,
                column_mapping=COLUMN_MAPPING,
                recipe_specification=RECIPE_SPEC,
                brand_controls=BRAND_CONTROLS,
                estimate=False,
            )
            tracker[arch] = {
                "dataset_id": dataset_id,
                "run_id": resp.run_id,
                "credits": resp.estimated_credits_consumed,
                "estimated_minutes": resp.estimated_minutes,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "status": "running",
            }
            print(f"  Run ID: {resp.run_id}")
            print(f"  Credits: {resp.estimated_credits_consumed}")
            print(f"  ETA: {resp.estimated_minutes:.0f} min")
        except Exception as e:
            print(f"  ERROR: {e}")
            tracker[arch] = {"dataset_id": dataset_id, "status": "error", "error": str(e)}

    # Save tracker
    os.makedirs(os.path.dirname(TRACKER_PATH), exist_ok=True)
    with open(TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2)

    print(f"\n{'='*50}")
    print(f"All jobs submitted. Tracker saved to:")
    print(f"  {TRACKER_PATH}")
    print(f"\nCheck status later with:")
    print(f"  python src/generators/adaptive_check.py")
    print(f"{'='*50}")


if __name__ == "__main__":
    submit_all()
