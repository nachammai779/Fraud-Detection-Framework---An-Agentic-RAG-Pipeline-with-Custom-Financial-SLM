"""Poll IEEE Adaption Labs jobs for status.

Reads the tracker written by adaption_submit_ieee.py and prints per-archetype
status. Updates the tracker in-place.

Usage:
    python -m src.sft_v3.adaption_check_ieee
"""
from __future__ import annotations
import json
import os
from pathlib import Path

from adaption import Adaption

TRACKER_PATH = Path("datasets/ieee_for_adaption/adaption_jobs.json")


def check_all() -> None:
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return
    if not TRACKER_PATH.exists():
        print(f"No tracker at {TRACKER_PATH}. Run adaption_submit_ieee.py first.")
        return

    tracker = json.loads(TRACKER_PATH.read_text())
    client = Adaption(api_key=api_key)

    print(f"{'Archetype':<13} {'Status':<12} {'Progress':<20} {'Dataset ID'}")
    print("-" * 70)

    all_done = True
    for arch, info in tracker.items():
        dataset_id = info["dataset_id"]
        try:
            status = client.datasets.get_status(dataset_id)
            s = status.status
            progress = ""
            if status.progress:
                p = status.progress
                progress = f"{p.processed_rows}/{p.total_rows}"
                if p.percent:
                    progress += f" ({p.percent:.0f}%)"
            print(f"  {arch:<11} {s:<12} {progress:<20} {dataset_id[:16]}...")
            tracker[arch]["status"] = s
            if s not in ("succeeded", "failed"):
                all_done = False
        except Exception as e:
            print(f"  {arch:<11} {'error':<12} {str(e)[:40]}")
            all_done = False

    TRACKER_PATH.write_text(json.dumps(tracker, indent=2))
    if all_done:
        print("\nAll jobs done. Run: python -m src.sft_v3.adaption_download_ieee")
    else:
        print("\nStill running. Re-run later.")


if __name__ == "__main__":
    check_all()