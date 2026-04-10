"""
adaptive_check.py
=================
Check status of all submitted adaptation jobs.

Usage:
    python adaptive_check.py
"""

import os
import sys
import json

from adaption import Adaption

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRACKER_PATH = os.path.join(PROJECT_ROOT, "datasets", "adaption_jobs.json")


def check_all():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return

    if not os.path.exists(TRACKER_PATH):
        print(f"No tracker found at {TRACKER_PATH}")
        print("Run adaptive_submit.py first.")
        return

    with open(TRACKER_PATH, "r") as f:
        tracker = json.load(f)

    client = Adaption(api_key=api_key)

    print(f"{'Archetype':<15} {'Status':<12} {'Progress':<20} {'Dataset ID'}")
    print("-" * 65)

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

            print(f"  {arch:<13} {s:<12} {progress:<20} {dataset_id[:16]}...")

            # Update tracker
            tracker[arch]["status"] = s
            if s not in ("succeeded", "failed"):
                all_done = False
        except Exception as e:
            print(f"  {arch:<13} {'error':<12} {str(e)[:40]}")
            all_done = False

    # Save updated tracker
    with open(TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2)

    if all_done:
        print(f"\nAll jobs complete. Run:")
        print(f"  python src/generators/adaptive_download.py")
    else:
        print(f"\nJobs still running. Check again later.")


if __name__ == "__main__":
    check_all()
