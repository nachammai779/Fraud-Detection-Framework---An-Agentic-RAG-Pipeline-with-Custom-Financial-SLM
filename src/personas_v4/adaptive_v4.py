"""
V4 narrative fill — mimics v1/v2 Adaption flow but with persona grounding on the prompt.

Takes datasets_v4/{archetype}/synthetic/transactions.parquet (22 cols incl. the 3 v3 columns),
builds persona-anchored prompts, and sends to Adaption Labs for narrative_text generation.

Four subcommands, same shape as src/generators/adaptive_reasoning.py:
  --estimate   dry-run: build the upload JSONL and estimate credits, no charge
  --submit     actually run the Adaption job (charges credits)
  --check      poll job status
  --download   fetch completed results + merge narrative_text into transactions_adapted.parquet

Inputs:
  datasets_v4/{archetype}/personas/persona_profiles.json
  datasets_v4/{archetype}/synthetic/transactions.parquet

Outputs (per archetype):
  datasets_v4/{archetype}/adaptive/for_adaption.jsonl       upload payload
  datasets_v4/{archetype}/adaptive/adapted_output.jsonl     download after job completes
  datasets_v4/{archetype}/adaptive/transactions_adapted.parquet  final merged result
  datasets_v4/{archetype}/adaptive/run_metadata.json        most-recent job metadata
  datasets_v4/adaptive_jobs.json                            all-jobs ledger

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
V4 = ROOT / "datasets_v4"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
JOB_TRACKER = V4 / "adaptive_jobs.json"


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
    arch_dir = V4 / archetype
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
    """Download an Adaption job's narratives and write to a phase-specific file.

    - Full-sized jobs (n_rows >= 1000) overwrite transactions_adapted.parquet.
    - MVP / sample jobs (n_rows < 1000) write to a distinct file
      transactions_adapted_phase2_mvp{N}.parquet so they don't clobber
      the overlay. Output carries full v4 metadata for the submitted rows
      only (no merge with the full 5000-row table).
    """
    arch_dir = V4 / archetype / "adaptive"
    meta = _load_meta(archetype)
    if not meta:
        raise RuntimeError(f"no run_metadata.json for {archetype}; submit + wait first")
    n_submitted = int(meta.get("n_rows", 0) or 0)
    is_mvp = 0 < n_submitted < 1000

    client = _get_client(api_key)
    content = client.datasets.download(meta["dataset_id"], file_format="jsonl")
    jsonl_name = f"adapted_output_phase2_mvp{n_submitted}.jsonl" if is_mvp else "adapted_output.jsonl"
    out_jsonl = arch_dir / jsonl_name
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

    # Merge into transactions — MVP path keeps only the submitted rows with full v4 metadata
    txns = pd.read_parquet(V4 / archetype / "synthetic" / "transactions.parquet")
    if is_mvp:
        # Inner join: keep only the ~50 submitted rows, attach fresh narrative
        merged = txns.merge(adapted[["data_uuid", "narrative_text"]], on="data_uuid", how="inner", suffixes=("", "_new"))
        if "narrative_text_new" in merged.columns:
            merged["narrative_text"] = merged["narrative_text_new"]
            merged = merged.drop(columns=["narrative_text_new"])
        out_parquet = arch_dir / f"transactions_adapted_phase2_mvp{n_submitted}.parquet"
    else:
        # Full-fill path: left-join, overwrite the main adapted file
        merged = txns.merge(adapted[["data_uuid", "narrative_text"]], on="data_uuid", how="left", suffixes=("", "_new"))
        if "narrative_text_new" in merged.columns:
            merged["narrative_text"] = merged["narrative_text_new"].fillna(merged["narrative_text"])
            merged = merged.drop(columns=["narrative_text_new"])
        out_parquet = arch_dir / "transactions_adapted.parquet"
    merged.to_parquet(out_parquet, index=False)
    fill_rate = merged["narrative_text"].astype(str).str.len().gt(0).mean()
    print(f"[{archetype}] wrote {out_parquet} ({len(merged)} rows, narrative fill rate: {fill_rate:.3f})")
    return {
        "archetype": archetype,
        "n_rows": len(merged),
        "narrative_fill_rate": float(fill_rate),
        "mvp": is_mvp,
        "output_path": str(out_parquet),
    }


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
    arch_dir = V4 / archetype / "adaptive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    (arch_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    tracker = {}
    if JOB_TRACKER.exists():
        tracker = json.loads(JOB_TRACKER.read_text(encoding="utf-8"))
    tracker.setdefault(archetype, []).append(meta)
    JOB_TRACKER.write_text(json.dumps(tracker, indent=2), encoding="utf-8")


def _load_meta(archetype: str) -> dict | None:
    p = V4 / archetype / "adaptive" / "run_metadata.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ── CLI ──────────────────────────────────────────────────────────────────────

# ── Combined-archetype path (one job for all 4 archetypes) ──────────────────

def build_combined_upload_jsonl(max_rows_total: int | None) -> tuple[Path, int, dict]:
    """Concatenate all 4 archetypes into a single JSONL.

    If max_rows_total is set, stratify equally across archetypes
    (max_rows_total // 4 rows per archetype).
    """
    per_arch = None
    if max_rows_total:
        per_arch = max_rows_total // len(ARCHETYPES)

    all_rows = []
    per_arch_counts = {}
    for arch in ARCHETYPES:
        arch_dir = V4 / arch
        personas = json.loads((arch_dir / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))["personas"]
        persona_index = {p["persona_id"]: p for p in personas}
        txns = pd.read_parquet(arch_dir / "synthetic" / "transactions.parquet")
        if per_arch:
            txns = txns.sample(min(per_arch, len(txns)), random_state=42).reset_index(drop=True)

        for _, r in txns.iterrows():
            persona = persona_index.get(r["persona_id"])
            if persona is None:
                continue
            prompt = build_prompt(persona, r, arch)
            all_rows.append({
                "prompt": prompt,
                "completion": "",
                "data_uuid": str(r.get("data_uuid", "")),
                "persona_id": r["persona_id"],
                "archetype": arch,
                "is_fraud": int(r.get("is_fraud", 0)),
                "language": r.get("language", ""),
                "fraud_vector_typology_ref": r.get("fraud_vector_typology_ref") or "",
            })
        per_arch_counts[arch] = len(txns)

    out_dir = V4 / "adaptive_combined"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "for_adaption.jsonl"
    pd.DataFrame(all_rows).to_json(out_path, orient="records", lines=True, force_ascii=False)
    return out_path, len(all_rows), per_arch_counts


def run_adaption_combined(api_key: str, max_rows_total: int | None, estimate_only: bool) -> dict:
    upload_path, n_rows, per_arch_counts = build_combined_upload_jsonl(max_rows_total)
    print(f"[combined] upload: {upload_path} ({n_rows} txns, per-archetype={per_arch_counts}, estimate_only={estimate_only})")

    client = _get_client(api_key)
    resp_up = client.datasets.upload_file(
        path=str(upload_path),
        name="fraud-combined-narrative-fill-v4",
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
            print(f"[combined] import not ready, retrying in 10s")
            time.sleep(10)
    if resp is None:
        raise RuntimeError(f"combined: dataset {dataset_id} still importing after 15 min")

    meta = {
        "archetype": "combined",
        "dataset_id": dataset_id,
        "run_id": getattr(resp, "run_id", None),
        "estimated_credits": getattr(resp, "estimated_credits_consumed", None),
        "estimated_minutes": getattr(resp, "estimated_minutes", None),
        "n_rows": n_rows,
        "per_archetype_counts": per_arch_counts,
        "estimate_only": estimate_only,
    }
    # Persist to a dedicated combined metadata file + the main job tracker
    out_dir = V4 / "adaptive_combined"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    tracker = {}
    if JOB_TRACKER.exists():
        tracker = json.loads(JOB_TRACKER.read_text(encoding="utf-8"))
    tracker.setdefault("combined", []).append(meta)
    JOB_TRACKER.write_text(json.dumps(tracker, indent=2), encoding="utf-8")
    return meta


def check_status_combined(api_key: str) -> dict:
    p = V4 / "adaptive_combined" / "run_metadata.json"
    if not p.exists():
        raise RuntimeError("no combined run_metadata.json; submit first")
    meta = json.loads(p.read_text(encoding="utf-8"))
    client = _get_client(api_key)
    status = client.datasets.get_status(meta["dataset_id"])
    return {"status": getattr(status, "status", None), "progress": str(getattr(status, "progress", "")), "meta": meta}


def download_combined_and_split(api_key: str) -> dict:
    p = V4 / "adaptive_combined" / "run_metadata.json"
    if not p.exists():
        raise RuntimeError("no combined run_metadata.json")
    meta = json.loads(p.read_text(encoding="utf-8"))
    client = _get_client(api_key)
    content = client.datasets.download(meta["dataset_id"], file_format="jsonl")
    (V4 / "adaptive_combined" / "adapted_output.jsonl").write_text(content, encoding="utf-8")
    print(f"[combined] downloaded {len(content)} bytes")

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
            "archetype": rec.get("archetype", ""),
            "persona_id": rec.get("persona_id", ""),
            "narrative_text": narrative,
        })
    adapted = pd.DataFrame(rows)

    # Split back by archetype, merge into each archetype's transactions
    summary = {"archetypes": {}}
    for arch in ARCHETYPES:
        sub = adapted[adapted["archetype"] == arch]
        txns = pd.read_parquet(V4 / arch / "synthetic" / "transactions.parquet")
        merged = txns.merge(sub[["data_uuid", "narrative_text"]], on="data_uuid", how="left", suffixes=("", "_new"))
        if "narrative_text_new" in merged.columns:
            merged["narrative_text"] = merged["narrative_text_new"].fillna(merged["narrative_text"])
            merged = merged.drop(columns=["narrative_text_new"])
        out = V4 / arch / "adaptive" / "transactions_adapted.parquet"
        merged.to_parquet(out, index=False)
        fill = merged["narrative_text"].astype(str).str.len().gt(0).mean()
        summary["archetypes"][arch] = {"n_rows": len(merged), "narrative_fill_rate": round(float(fill), 3), "out": str(out)}
        print(f"[{arch}] {len(merged)} rows, narrative_fill={fill:.3f} -> {out}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archetype", choices=ARCHETYPES)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--combined", action="store_true",
                        help="submit all 4 archetypes as ONE Adaption job (single queue position)")
    parser.add_argument("--max_rows", type=int, default=None,
                        help="per-archetype cap; in --combined mode this is the total-cap and is divided by 4")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--estimate", action="store_true")
    grp.add_argument("--submit",   action="store_true")
    grp.add_argument("--check",    action="store_true")
    grp.add_argument("--download", action="store_true")
    args = parser.parse_args()

    if not args.combined and not args.all and not args.archetype:
        parser.error("specify --archetype, --all, or --combined")

    if not args.estimate:
        api_key = os.environ.get("ADAPTION_API_KEY")
        if not api_key:
            print("ADAPTION_API_KEY not set", file=sys.stderr)
            return 1
    else:
        api_key = os.environ.get("ADAPTION_API_KEY", "")

    # --- Combined mode (single job for all 4 archetypes) ---
    if args.combined:
        if args.estimate:
            upload_path, n_rows, per_arch = build_combined_upload_jsonl(args.max_rows)
            print(f"[combined] upload-JSONL built: {upload_path} ({n_rows} rows, per-archetype={per_arch})")
            if api_key:
                m = run_adaption_combined(api_key, args.max_rows, estimate_only=True)
                print(json.dumps(m, indent=2))
            else:
                print(f"[combined] (no ADAPTION_API_KEY; JSONL built but credit-estimate skipped)")
        elif args.submit:
            m = run_adaption_combined(api_key, args.max_rows, estimate_only=False)
            print(json.dumps(m, indent=2))
        elif args.check:
            s = check_status_combined(api_key)
            print(json.dumps(s, indent=2, default=str))
        elif args.download:
            s = download_combined_and_split(api_key)
            print(json.dumps(s, indent=2))
        return 0

    # --- Per-archetype mode (original behaviour) ---
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
