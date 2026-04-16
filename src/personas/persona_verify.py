"""
Day 8: Second-pass persona verification.

For each generated record, ask Adaptive Data: "Is this transaction behaviorally
coherent with the persona it was conditioned on?" Records that fail coherence
checks are flagged for re-generation.

Inputs:
  datasets_v2/{archetype}/synthetic/transactions.parquet  (TabDDPM v2 output, preferred)
  datasets/{archetype}/synthetic/transactions.parquet     (v1 fallback, persona_id randomly assigned)
  datasets_v2/{archetype}/personas/persona_profiles.json  (source personas)

Outputs (per archetype):
  datasets_v2/{archetype}/persona_verification/for_adaption.jsonl
  datasets_v2/{archetype}/persona_verification/run_metadata.json

Usage:
  export ADAPTION_API_KEY=pt_live_...
  python src/personas/persona_verify.py --archetype remittance --estimate
  python src/personas/persona_verify.py --all --sample 200
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import pandas as pd
from adaption import Adaption, ConflictError

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT_V2 = ROOT / "datasets_v2"
DATA_ROOT_V1 = ROOT / "datasets"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
JOB_TRACKER = DATA_ROOT_V2 / "persona_verify_jobs.json"


def locate_transactions(archetype: str) -> tuple[Path, str]:
    v2 = DATA_ROOT_V2 / archetype / "synthetic" / "transactions.parquet"
    if v2.exists():
        return v2, "v2"
    v1 = DATA_ROOT_V1 / archetype / "synthetic" / "transactions.parquet"
    if v1.exists():
        return v1, "v1_fallback"
    raise FileNotFoundError(f"no synthetic transactions for {archetype}")


def build_upload_jsonl(archetype: str, sample_n: int) -> tuple[Path, int]:
    arch_dir = DATA_ROOT_V2 / archetype
    txn_path, source = locate_transactions(archetype)
    txns = pd.read_parquet(txn_path)
    personas = json.loads((arch_dir / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))
    persona_index = {p["persona_id"]: p for p in personas["personas"]}

    if "persona_id" not in txns.columns:
        rng = random.Random(42)
        ids = list(persona_index.keys())
        txns["persona_id"] = [rng.choice(ids) for _ in range(len(txns))]

    sample = txns.sample(min(sample_n, len(txns)), random_state=42)

    rows = []
    for _, row in sample.iterrows():
        persona = persona_index.get(row["persona_id"])
        if persona is None:
            continue
        txn_dict = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
        prompt = (
            f"Score the behavioral coherence (0.0-1.0) of this transaction against the persona. "
            f"Return JSON {{\"coherence_score\": float, \"violations\": [str], \"rationale\": str}}. "
            f"Persona:\n{json.dumps(persona, ensure_ascii=False)}\n\n"
            f"Transaction:\n{json.dumps(txn_dict, ensure_ascii=False, default=str)}"
        )
        rows.append({
            "persona_id": row["persona_id"],
            "data_uuid": str(row.get("data_uuid", "")),
            "archetype": archetype,
            "prompt": prompt,
            "completion": "",
            "source": source,
        })

    out_dir = arch_dir / "persona_verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "for_adaption.jsonl"
    pd.DataFrame(rows).to_json(out_path, orient="records", lines=True, force_ascii=False)
    return out_path, len(rows)


def submit(archetype: str, api_key: str, sample_n: int, estimate_only: bool) -> dict:
    upload_path, n_rows = build_upload_jsonl(archetype, sample_n)
    print(f"[{archetype}] upload: {upload_path} ({n_rows} txns)")

    client = Adaption(api_key=api_key)
    upload_resp = client.datasets.upload_file(
        path=str(upload_path),
        name=f"fraud-{archetype}-persona-verify-v2",
    )
    dataset_id = upload_resp.dataset_id

    column_mapping = {
        "prompt": "prompt",
        "completion": "completion",
        "context": ["archetype", "persona_id", "data_uuid", "source"],
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
    brand_controls = {"length": "concise", "hallucination_mitigation": True}

    deadline = time.time() + 900
    resp = None
    while time.time() < deadline:
        try:
            resp = client.datasets.run(
                dataset_id=dataset_id,
                column_mapping=column_mapping,
                recipe_specification=recipe_spec,
                brand_controls=brand_controls,
                job_specification={},
                estimate=estimate_only,
            )
            break
        except ConflictError:
            print(f"[{archetype}] import not ready, retrying in 10s")
            time.sleep(10)
    if resp is None:
        raise RuntimeError(f"{archetype}: dataset {dataset_id} still importing after 15 min")

    metadata = {
        "archetype": archetype,
        "dataset_id": dataset_id,
        "run_id": getattr(resp, "run_id", None),
        "estimated_credits": getattr(resp, "estimated_credits_consumed", None),
        "estimated_minutes": getattr(resp, "estimated_minutes", None),
        "n_rows": n_rows,
        "estimate_only": estimate_only,
    }
    (DATA_ROOT_V2 / archetype / "persona_verification" / "run_metadata.json").write_text(
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
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--estimate", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ADAPTION_API_KEY not set", file=sys.stderr)
        return 1
    if not args.all and not args.archetype:
        parser.error("specify --archetype or --all")

    targets = ARCHETYPES if args.all else [args.archetype]
    for arch in targets:
        meta = submit(arch, api_key, args.sample, estimate_only=args.estimate)
        print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())