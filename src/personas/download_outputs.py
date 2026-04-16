"""
Download completed Adaption Labs outputs for v2 pipeline.

Pulls both:
  - Expand-World results -> datasets_v2/{archetype}/expanded_world/adapted_output.jsonl
  - Persona-Verify results -> datasets_v2/{archetype}/persona_verification/adapted_output.jsonl

Reads dataset IDs from expand_world_jobs.json and persona_verify_jobs.json (latest job
per archetype). Also writes evaluation scores to evaluation.json alongside each output.

Usage:
  export ADAPTION_API_KEY=pt_live_...
  python src/personas/download_outputs.py --stage expand_world
  python src/personas/download_outputs.py --stage persona_verify
  python src/personas/download_outputs.py --all
"""

import argparse
import json
import os
import sys
from pathlib import Path

from adaption import Adaption

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "datasets_v2"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]

STAGES = {
    "expand_world": {
        "tracker": DATA_ROOT / "expand_world_jobs.json",
        "subdir": "expanded_world",
    },
    "persona_verify": {
        "tracker": DATA_ROOT / "persona_verify_jobs.json",
        "subdir": "persona_verification",
    },
}


def latest_dataset_id(tracker_path: Path, archetype: str) -> str:
    tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
    jobs = tracker.get(archetype, [])
    if not jobs:
        raise KeyError(f"no jobs tracked for {archetype} in {tracker_path}")
    last = jobs[-1]
    return last["dataset_id"] if isinstance(last, dict) else last


def download_stage(stage: str, client: Adaption) -> None:
    cfg = STAGES[stage]
    for arch in ARCHETYPES:
        try:
            dataset_id = latest_dataset_id(cfg["tracker"], arch)
        except KeyError as e:
            print(f"[{arch}/{stage}] skip: {e}")
            continue

        out_dir = DATA_ROOT / arch / cfg["subdir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        status = client.datasets.get_status(dataset_id)
        print(f"[{arch}/{stage}] dataset={dataset_id} status={status.status} rows={status.progress.processed_rows}/{status.progress.total_rows}")
        if status.status != "succeeded":
            print(f"[{arch}/{stage}] not ready, skipping download")
            continue

        content = client.datasets.download(dataset_id, file_format="jsonl")
        out_path = out_dir / "adapted_output.jsonl"
        out_path.write_text(content, encoding="utf-8")
        print(f"[{arch}/{stage}] wrote {out_path} ({len(content)} bytes)")

        try:
            evaluation = client.datasets.get_evaluation(dataset_id)
            eval_dict = evaluation.model_dump() if hasattr(evaluation, "model_dump") else evaluation.to_dict()
            (out_dir / "evaluation.json").write_text(json.dumps(eval_dict, indent=2, default=str), encoding="utf-8")
            q = eval_dict.get("quality") or {}
            if q:
                print(f"[{arch}/{stage}] quality: {q}")
        except Exception as e:
            print(f"[{arch}/{stage}] evaluation unavailable: {e}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=list(STAGES))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ADAPTION_API_KEY not set", file=sys.stderr)
        return 1
    if not args.all and not args.stage:
        parser.error("specify --stage or --all")

    client = Adaption(api_key=api_key)
    stages = list(STAGES) if args.all else [args.stage]
    for stage in stages:
        download_stage(stage, client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())