"""
v4.1 — one-shot Adaption wrapper that bundles empties re-prompt + missing-
typology narratives into a single Adaption job.

Subcommands:
  --estimate   build merged JSONL, upload, request a credit estimate
  --submit     build merged JSONL, upload, submit the run
  --check      poll status for the run
  --download   download results, split by source, merge into the right places

Bundled inputs (both must already exist):
  datasets_v4/v4_1/empties_reprompt.jsonl                  (52 rows)
  datasets_v4/v4_1/missing_typology_for_adaption.jsonl     (300 rows)

Bundled upload:
  datasets_v4/v4_1/combined_upload.jsonl

Job state:
  datasets_v4/v4_1/run_metadata.json

Envvar required for all phases: ADAPTION_API_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"
V41 = V4 / "v4_1"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]

EMPTIES = V41 / "empties_reprompt.jsonl"
MISSING = V41 / "missing_typology_for_adaption.jsonl"
MERGED = V41 / "combined_upload.jsonl"
META = V41 / "run_metadata.json"
OUTPUT = V41 / "adapted_output.jsonl"


def _client():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: ADAPTION_API_KEY not set")
    from adaption import Adaption
    return Adaption(api_key=api_key)


def _build_merged() -> tuple[int, int]:
    if not EMPTIES.exists():
        raise SystemExit(f"missing {EMPTIES} — run build_v4_1_reprompt.py first")
    if not MISSING.exists():
        raise SystemExit(f"missing {MISSING} — run v4_1_add_missing_typologies.py first")
    V41.mkdir(parents=True, exist_ok=True)
    n_emp = n_mis = 0
    with MERGED.open("w", encoding="utf-8") as out:
        for src_path, tag in [(EMPTIES, "empty_refill"), (MISSING, "missing_typology")]:
            with src_path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    r["v41_source"] = tag
                    out.write(json.dumps(r, ensure_ascii=False) + "\n")
                    if tag == "empty_refill":
                        n_emp += 1
                    else:
                        n_mis += 1
    print(f"merged upload: {MERGED}  (empties={n_emp}, missing_typology={n_mis}, total={n_emp+n_mis})")
    return n_emp, n_mis


def _run_kwargs(dataset_id: str, estimate: bool) -> dict:
    return dict(
        dataset_id=dataset_id,
        column_mapping={
            "prompt": "prompt",
            "completion": "completion",
            "context": ["persona_id", "archetype", "is_fraud", "language",
                        "fraud_vector_typology_ref", "v41_source"],
        },
        recipe_specification={
            "version": "v1",
            "recipes": {
                "deduplication": False,
                "prompt_rephrase": True,
                "reasoning_traces": False,
                "preference_pairs": False,
                "prompt_metadata_injection": True,
            },
        },
        brand_controls={"length": "detailed", "hallucination_mitigation": False},
        estimate=estimate,
    )


def do_estimate():
    _build_merged()
    client = _client()
    up = client.datasets.upload_file(path=str(MERGED), name="fraud-v4_1-combined")
    resp = client.datasets.run(**_run_kwargs(up.dataset_id, estimate=True))
    print(f"dataset_id: {up.dataset_id}")
    print(f"credits:    {resp.estimated_credits_consumed}")
    print(f"minutes:    {resp.estimated_minutes:.0f}")


def do_submit():
    n_emp, n_mis = _build_merged()
    client = _client()
    up = client.datasets.upload_file(path=str(MERGED), name="fraud-v4_1-combined")
    resp = client.datasets.run(**_run_kwargs(up.dataset_id, estimate=False))
    META.write_text(json.dumps({
        "dataset_id": up.dataset_id,
        "run_id": resp.run_id,
        "credits": resp.estimated_credits_consumed,
        "estimated_minutes": resp.estimated_minutes,
        "n_empties": n_emp,
        "n_missing_typology": n_mis,
        "status": "running",
    }, indent=2), encoding="utf-8")
    print(f"dataset_id: {up.dataset_id}")
    print(f"run_id:     {resp.run_id}")
    print(f"credits:    {resp.estimated_credits_consumed}")
    print(f"ETA:        {resp.estimated_minutes:.0f} min")
    print(f"metadata:   {META}")


def do_check():
    if not META.exists():
        raise SystemExit(f"no {META} — run --submit first")
    meta = json.loads(META.read_text(encoding="utf-8"))
    client = _client()
    st = client.datasets.get_status(meta["dataset_id"])
    print(f"status: {st.status}")
    if st.progress:
        print(f"progress: {st.progress.processed_rows}/{st.progress.total_rows}")
    meta["status"] = st.status
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _merge_empties(narrs_by_uuid: dict[str, str]) -> int:
    filled_total = 0
    for arch in ARCHETYPES:
        p = V4 / arch / "adaptive" / "transactions_adapted.parquet"
        df = pd.read_parquet(p)
        mask = df["data_uuid"].isin(narrs_by_uuid)
        if not mask.any():
            continue
        changed = 0
        for idx in df.index[mask]:
            u = df.at[idx, "data_uuid"]
            new_txt = str(narrs_by_uuid[u])[:2000]
            if new_txt:
                df.at[idx, "narrative_text"] = new_txt
                changed += 1
        if changed:
            df.to_parquet(p, index=False, engine="pyarrow")
            print(f"[{arch}] empties refilled: {changed}")
            filled_total += changed
    return filled_total


def _merge_missing(narrs_by_uuid: dict[str, str]) -> int:
    synth_path = V41 / "missing_typology_rows.parquet"
    if not synth_path.exists():
        raise SystemExit(f"missing {synth_path} — run v4_1_add_missing_typologies.py first")
    synth = pd.read_parquet(synth_path)
    synth["narrative_text"] = synth["data_uuid"].map(lambda u: narrs_by_uuid.get(u, synth["narrative_text"].iloc[0] if False else ""))
    # Be explicit: only set from narrs_by_uuid, keep '' for misses
    synth["narrative_text"] = synth["data_uuid"].map(lambda u: narrs_by_uuid.get(u, ""))
    synth.to_parquet(synth_path, index=False, engine="pyarrow")
    filled = int((synth["narrative_text"].astype(str).str.len() > 0).sum())
    print(f"synth rows narratives filled: {filled}/{len(synth)}")

    appended = 0
    for arch in ARCHETYPES:
        add = synth[synth["archetype"] == arch]
        if add.empty:
            continue
        main_path = V4 / arch / "adaptive" / "transactions_adapted.parquet"
        main = pd.read_parquet(main_path)
        # Only append uuids that aren't already in main (idempotent)
        add = add[~add["data_uuid"].isin(main["data_uuid"])]
        if add.empty:
            continue
        for c in main.columns:
            if c not in add.columns:
                add[c] = pd.NA
        add = add[main.columns]
        merged = pd.concat([main, add], ignore_index=True)
        merged.to_parquet(main_path, index=False, engine="pyarrow")
        print(f"[{arch}] appended {len(add)} missing-typology rows (now {len(merged)})")
        appended += len(add)
    return appended


def do_download():
    if not META.exists():
        raise SystemExit(f"no {META} — run --submit first")
    meta = json.loads(META.read_text(encoding="utf-8"))
    client = _client()
    st = client.datasets.get_status(meta["dataset_id"])
    if st.status != "succeeded":
        print(f"status={st.status} — not ready")
        return
    content = client.datasets.download(meta["dataset_id"], file_format="jsonl")
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"downloaded: {OUTPUT} ({len(content)} bytes)")

    # Parse and split by v41_source tag
    by_source: dict[str, dict[str, str]] = {"empty_refill": {}, "missing_typology": {}}
    for line in content.splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        u = r.get("data_uuid", "")
        txt = r.get("enhanced_completion") or r.get("completion") or ""
        if isinstance(txt, dict):
            txt = json.dumps(txt, ensure_ascii=False)
        tag = r.get("v41_source", "")
        if u and txt and tag in by_source:
            by_source[tag][u] = str(txt)
    print(f"parsed: empties={len(by_source['empty_refill'])}, "
          f"missing_typology={len(by_source['missing_typology'])}")

    n1 = _merge_empties(by_source["empty_refill"])
    n2 = _merge_missing(by_source["missing_typology"])

    # Rebuild bundle
    frames = [pd.read_parquet(V4 / a / "adaptive" / "transactions_adapted.parquet") for a in ARCHETYPES]
    bundle = pd.concat(frames, ignore_index=True)
    bp = V4 / "exports" / "transactions_v4_20k.parquet"
    bc = V4 / "exports" / "transactions_v4_20k.csv"
    if bp.exists():
        existing = pd.read_parquet(bp)
        cols = [c for c in existing.columns if c in bundle.columns] + \
               [c for c in bundle.columns if c not in existing.columns]
        bundle = bundle[cols]
    bundle.to_parquet(bp, index=False, engine="pyarrow")
    bundle.to_csv(bc, index=False)
    print(f"bundle rebuilt: {bp} ({len(bundle)} rows)")

    fr = bundle[bundle["is_fraud"] == 1]
    codes = fr["fraud_vector_typology_ref"].dropna().astype(str)
    codes = codes[codes.str.len() > 0]
    empties_now = int((bundle["narrative_text"].fillna("").astype(str).str.len() == 0).sum())
    print(f"\npost-merge summary:")
    print(f"  empties filled:         {n1}")
    print(f"  missing-typology added: {n2}")
    print(f"  distinct typology codes: {codes.nunique()}")
    print(f"  empty narratives remaining: {empties_now}")

    meta["status"] = "downloaded"
    meta["empties_filled"] = n1
    meta["missing_typology_appended"] = n2
    meta["final_typology_codes"] = int(codes.nunique())
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--estimate", action="store_true")
    g.add_argument("--submit", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--download", action="store_true")
    args = ap.parse_args()

    if args.estimate:
        do_estimate()
    elif args.submit:
        do_submit()
    elif args.check:
        do_check()
    elif args.download:
        do_download()


if __name__ == "__main__":
    main()