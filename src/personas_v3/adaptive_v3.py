"""
V3 narrative fill — mimics v1/v2 Adaption flow but with persona grounding on the prompt.

Takes datasets_v3/{archetype}/synthetic/transactions.parquet (22 cols incl. the 3 v3 columns),
builds persona-anchored prompts, and sends to Adaption Labs for narrative_text generation.

Four subcommands, same shape as src/generators/adaptive_reasoning.py:
  --estimate   dry-run: build the upload JSONL and estimate credits, no charge
  --submit     actually run the Adaption job (charges credits)
  --check      poll job status
  --download   fetch completed results + merge narrative_text into transactions_adapted.parquet

Inputs:
  datasets_v3/{archetype}/personas/persona_profiles.json
  datasets_v3/{archetype}/synthetic/transactions.parquet

Outputs (per archetype):
  datasets_v3/{archetype}/adaptive/for_adaption.jsonl       upload payload
  datasets_v3/{archetype}/adaptive/adapted_output.jsonl     download after job completes
  datasets_v3/{archetype}/adaptive/transactions_adapted.parquet  final merged result
  datasets_v3/{archetype}/adaptive/run_metadata.json        most-recent job metadata
  datasets_v3/adaptive_jobs.json                            all-jobs ledger

Envvar required for --submit/--check/--download:
  ADAPTION_API_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "datasets_v3"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
JOB_TRACKER = V3 / "adaptive_jobs.json"


# ── Prompt construction ──────────────────────────────────────────────────────

def build_prompt(persona: dict, row: pd.Series, archetype: str) -> str:
    """Persona-anchored prompt for a single transaction row."""
    is_fraud = int(row.get("is_fraud", 0))
    fraud_label = "fraudulent / attempted scam" if is_fraud else "legitimate"

    persona_summary = persona.get("summary", "") or ""
    persona_languages = persona.get("language_mix") or ["en"]
    primary_lang = row.get("language") or persona_languages[0]

    txn_details = {
        "amount_usd": round(float(row.get("transaction_amount_usd", 0)), 2),
        "fee_usd": round(float(row.get("fee_amount_usd", 0)), 2),
        "instrument": row.get("instrument", "unknown"),
        "fraud_vector": row.get("fraud_vector", ""),
        "hour_of_day": int(row.get("hour_of_day", 12)),
        "day_of_week": row.get("day_of_week_name", ""),
        "days_since_last": int(row.get("days_since_last_txn", 0)),
        "is_fraud": is_fraud,
    }

    typology_ref = row.get("fraud_vector_typology_ref")
    typology_line = f"FinCEN typology: {typology_ref}. " if typology_ref else ""

    return (
        f"Write a realistic first-person narrative (3-5 sentences) from this persona describing "
        f"a {fraud_label} transaction that just occurred. Use the persona's voice, cultural context, "
        f"and primary language. If fraudulent, hint at the scam mechanic without naming it explicitly.\n\n"
        f"Persona ({archetype}):\n{persona_summary}\n\n"
        f"Transaction:\n{json.dumps(txn_details, ensure_ascii=False)}\n\n"
        f"{typology_line}"
        f"Language to write in: {primary_lang}. "
        f"Include one emotional beat consistent with the transaction (relief, worry, gratitude, shame, "
        f"obligation). Return just the narrative text, no preamble."
    )


def build_upload_jsonl(archetype: str, max_rows: int | None) -> tuple[Path, int]:
    arch_dir = V3 / archetype
    personas = json.loads((arch_dir / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))["personas"]
    persona_index = {p["persona_id"]: p for p in personas}

    txns = pd.read_parquet(arch_dir / "synthetic" / "transactions.parquet")
    if max_rows:
        txns = txns.sample(min(max_rows, len(txns)), random_state=42).reset_index(drop=True)

    rows = []
    for _, r in txns.iterrows():
        persona = persona_index.get(r["persona_id"])
        if persona is None:
            continue
        prompt = build_prompt(persona, r, archetype)
        rows.append({
            "prompt": prompt,
            "completion": "",
            "data_uuid": str(r.get("data_uuid", "")),
            "persona_id": r["persona_id"],
            "archetype": archetype,
            "is_fraud": int(r.get("is_fraud", 0)),
            "language": r.get("language", ""),
            "fraud_vector_typology_ref": r.get("fraud_vector_typology_ref") or "",
        })

    out_dir = arch_dir / "adaptive"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "for_adaption.jsonl"
    pd.DataFrame(rows).to_json(out_path, orient="records", lines=True, force_ascii=False)
    return out_path, len(rows)


# ── Adaption client wrappers ─────────────────────────────────────────────────

def _get_client(api_key: str):
    from adaption import Adaption
    return Adaption(api_key=api_key)


def run_adaption(archetype: str, api_key: str, max_rows: int | None, estimate_only: bool) -> dict:
    upload_path, n_rows = build_upload_jsonl(archetype, max_rows)
    print(f"[{archetype}] upload: {upload_path} ({n_rows} txns, estimate_only={estimate_only})")

    client = _get_client(api_key)
    resp_up = client.datasets.upload_file(
        path=str(upload_path),
        name=f"fraud-{archetype}-narrative-fill-v3",
    )
    dataset_id = resp_up.dataset_id

    column_mapping = {
        "prompt": "prompt",
        "completion": "completion",
        "context": ["archetype", "persona_id", "data_uuid", "is_fraud", "language", "fraud_vector_typology_ref"],
    }
    recipe_spec = {
        "version": "v1",
        "recipes": {
            "deduplication": False,
            "prompt_rephrase": False,
            "reasoning_traces": False,
            "preference_pairs": False,
            "prompt_metadata_injection": True,
        },
    }
    brand_controls = {"length": "concise", "hallucination_mitigation": True}

    from adaption import ConflictError
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

    meta = {
        "archetype": archetype,
        "dataset_id": dataset_id,
        "run_id": getattr(resp, "run_id", None),
        "estimated_credits": getattr(resp, "estimated_credits_consumed", None),
        "estimated_minutes": getattr(resp, "estimated_minutes", None),
        "n_rows": n_rows,
        "estimate_only": estimate_only,
    }
    _save_meta(archetype, meta)
    return meta


def check_status(archetype: str, api_key: str) -> dict:
    meta = _load_meta(archetype)
    if not meta:
        raise RuntimeError(f"no run_metadata.json for {archetype}; submit first")
    client = _get_client(api_key)
    status = client.datasets.get_status(meta["dataset_id"])
    return {"archetype": archetype, "status": getattr(status, "status", None), "meta": meta}


def download_and_merge(archetype: str, api_key: str) -> dict:
    arch_dir = V3 / archetype / "adaptive"
    meta = _load_meta(archetype)
    if not meta:
        raise RuntimeError(f"no run_metadata.json for {archetype}; submit + wait first")
    client = _get_client(api_key)
    content = client.datasets.download(meta["dataset_id"], file_format="jsonl")
    out_jsonl = arch_dir / "adapted_output.jsonl"
    out_jsonl.write_text(content, encoding="utf-8")
    print(f"[{archetype}] downloaded {len(content)} bytes -> {out_jsonl}")

    # Parse
    rows = []
    for line in content.splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        narrative = rec.get("enhanced_completion") or rec.get("completion") or ""
        if isinstance(narrative, dict):
            narrative = json.dumps(narrative, ensure_ascii=False)
        narrative = _strip_json_wrapper(narrative)
        rows.append({
            "data_uuid": rec.get("data_uuid", ""),
            "persona_id": rec.get("persona_id", ""),
            "narrative_text": narrative,
        })
    adapted = pd.DataFrame(rows)

    # Merge into transactions
    txns = pd.read_parquet(V3 / archetype / "synthetic" / "transactions.parquet")
    merged = txns.merge(adapted[["data_uuid", "narrative_text"]], on="data_uuid", how="left", suffixes=("", "_new"))
    if "narrative_text_new" in merged.columns:
        merged["narrative_text"] = merged["narrative_text_new"].fillna(merged["narrative_text"])
        merged = merged.drop(columns=["narrative_text_new"])
    out_parquet = arch_dir / "transactions_adapted.parquet"
    merged.to_parquet(out_parquet, index=False)
    fill_rate = merged["narrative_text"].astype(str).str.len().gt(0).mean()
    print(f"[{archetype}] wrote {out_parquet} (narrative fill rate: {fill_rate:.3f})")
    return {"archetype": archetype, "n_rows": len(merged), "narrative_fill_rate": float(fill_rate)}


def _strip_json_wrapper(blob: str) -> str:
    """Adaption sometimes wraps returns in a json block. Strip if present."""
    if not blob:
        return ""
    m = re.search(r"```(?:json)?\s*(.*?)```", blob, re.DOTALL)
    if m:
        return m.group(1).strip()
    return blob.strip()


# ── Job tracker persistence ─────────────────────────────────────────────────

def _save_meta(archetype: str, meta: dict) -> None:
    arch_dir = V3 / archetype / "adaptive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    (arch_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    tracker = {}
    if JOB_TRACKER.exists():
        tracker = json.loads(JOB_TRACKER.read_text(encoding="utf-8"))
    tracker.setdefault(archetype, []).append(meta)
    JOB_TRACKER.write_text(json.dumps(tracker, indent=2), encoding="utf-8")


def _load_meta(archetype: str) -> dict | None:
    p = V3 / archetype / "adaptive" / "run_metadata.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archetype", choices=ARCHETYPES)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--max_rows", type=int, default=None,
                        help="cap rows submitted for cost control (e.g. --max_rows 200)")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--estimate", action="store_true", help="build JSONL + dry-run credit estimate, no charge")
    grp.add_argument("--submit",   action="store_true", help="actually run the job, credits charged")
    grp.add_argument("--check",    action="store_true", help="poll job status")
    grp.add_argument("--download", action="store_true", help="download completed results + merge narrative_text")
    args = parser.parse_args()

    if not args.all and not args.archetype:
        parser.error("specify --archetype or --all")

    if not args.estimate:
        api_key = os.environ.get("ADAPTION_API_KEY")
        if not api_key:
            print("ADAPTION_API_KEY not set", file=sys.stderr)
            return 1
    else:
        api_key = os.environ.get("ADAPTION_API_KEY", "")

    targets = ARCHETYPES if args.all else [args.archetype]
    for arch in targets:
        if args.estimate:
            upload_path, n_rows = build_upload_jsonl(arch, args.max_rows)
            print(f"[{arch}] upload-JSONL built: {upload_path} ({n_rows} rows)")
            if api_key:
                m = run_adaption(arch, api_key, args.max_rows, estimate_only=True)
                print(json.dumps(m, indent=2))
            else:
                print(f"[{arch}] (no ADAPTION_API_KEY; JSONL built but credit-estimate skipped)")
        elif args.submit:
            m = run_adaption(arch, api_key, args.max_rows, estimate_only=False)
            print(json.dumps(m, indent=2))
        elif args.check:
            s = check_status(arch, api_key)
            print(json.dumps(s, indent=2, default=str))
        elif args.download:
            s = download_and_merge(arch, api_key)
            print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
