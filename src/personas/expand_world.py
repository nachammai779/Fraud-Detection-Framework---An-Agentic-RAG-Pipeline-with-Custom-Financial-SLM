"""
For each persona, Adaptive Data returns an expanded conditioning schema covering:
  - full transaction calendar (dates, amounts, merchants)
  - device fingerprint evolution
  - remittance / cashout cadence
  - income seasonality
  - communication patterns (call/SMS/WhatsApp)

Output (per archetype):
  datasets_v2/{archetype}/expanded_world/for_adaption.jsonl   prompt rows uploaded
  datasets_v2/{archetype}/expanded_world/run_metadata.json    dataset_id, run_id

Usage:
  export ADAPTION_API_KEY=pt_live_...
  python src/personas/expand_world.py --archetype remittance --estimate
  python src/personas/expand_world.py --all
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
from adaption import Adaption

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "datasets_v2"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
JOB_TRACKER = DATA_ROOT / "expand_world_jobs.json"

EXPANSION_TARGETS = [
    "transaction_calendar",
    "device_fingerprint_evolution",
    "remittance_cadence",
    "income_seasonality",
    "communication_patterns",
]


def load_personas(archetype: str) -> dict:
    return json.loads((DATA_ROOT / archetype / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))


def persona_to_prompt_row(persona: dict, archetype: str, world_dimensions: list) -> dict:
    prompt = (
        f"Expand the following {archetype} persona into a structured conditioning schema "
        f"for synthetic transaction generation. Return JSON covering: "
        f"{', '.join(EXPANSION_TARGETS)}. "
        f"Anchor every field to the persona's world dimensions: {', '.join(world_dimensions)}. "
        f"Persona:\n{json.dumps(persona, ensure_ascii=False)}"
    )
    return {
        "persona_id": persona["persona_id"],
        "archetype": archetype,
        "prompt": prompt,
        "completion": "",
        "world_dimensions": ",".join(world_dimensions),
    }


def build_upload_jsonl(archetype: str) -> Path:
    personas = load_personas(archetype)
    rows = [persona_to_prompt_row(p, archetype, personas["key_world_dimensions"]) for p in personas["personas"]]
    out_dir = DATA_ROOT / archetype / "expanded_world"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "for_adaption.jsonl"
    pd.DataFrame(rows).to_json(out_path, orient="records", lines=True, force_ascii=False)
    return out_path


def submit(archetype: str, api_key: str, estimate_only: bool) -> dict:
    upload_path = build_upload_jsonl(archetype)
    n_rows = sum(1 for _ in upload_path.open(encoding="utf-8"))
    print(f"[{archetype}] upload file: {upload_path} ({n_rows} personas)")

    client = Adaption(api_key=api_key)

    upload_resp = client.datasets.upload_file(
        path=str(upload_path),
        name=f"fraud-{archetype}-personas-expand-world-v2",
    )
    dataset_id = upload_resp.dataset_id
    print(f"[{archetype}] dataset_id: {dataset_id}")

    column_mapping = {
        "prompt": "prompt",
        "completion": "completion",
        "context": ["archetype", "persona_id", "world_dimensions"],
    }
    recipe_spec = {
        "version": "v1",
        "recipes": {
            "deduplication": False,
            "prompt_rephrase": False,
            "reasoning_traces": True,
            "preference_pairs": False,
            "prompt_metadata_injection": True,
        },
    }
    brand_controls = {"length": "detailed", "hallucination_mitigation": True}

    resp = client.datasets.run(
        dataset_id=dataset_id,
        column_mapping=column_mapping,
        recipe_specification=recipe_spec,
        brand_controls=brand_controls,
        job_specification={},
        estimate=estimate_only,
    )

    metadata = {
        "archetype": archetype,
        "dataset_id": dataset_id,
        "run_id": getattr(resp, "run_id", None),
        "estimated_credits": getattr(resp, "estimated_credits_consumed", None),
        "estimated_minutes": getattr(resp, "estimated_minutes", None),
        "n_personas": n_rows,
        "estimate_only": estimate_only,
    }
    (DATA_ROOT / archetype / "expanded_world" / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    _record_job(archetype, metadata)
    return metadata


def _record_job(archetype: str, metadata: dict) -> None:
    tracker = {}
    if JOB_TRACKER.exists():
        tracker = json.loads(JOB_TRACKER.read_text(encoding="utf-8"))
    tracker.setdefault(archetype, []).append(metadata)
    JOB_TRACKER.write_text(json.dumps(tracker, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archetype", choices=ARCHETYPES)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--estimate", action="store_true", help="dry-run credit estimate only")
    args = parser.parse_args()

    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ADAPTION_API_KEY not set", file=sys.stderr)
        return 1

    if not args.all and not args.archetype:
        parser.error("specify --archetype or --all")

    targets = ARCHETYPES if args.all else [args.archetype]
    for arch in targets:
        meta = submit(arch, api_key, estimate_only=args.estimate)
        print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())