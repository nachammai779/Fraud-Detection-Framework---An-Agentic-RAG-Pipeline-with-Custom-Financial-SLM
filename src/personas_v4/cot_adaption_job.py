"""
CoT reasoning Adaption wrapper for the fraud + matched-negatives subset.

Subcommands:
  --estimate   upload, request credit estimate (no run)
  --submit     upload + submit with reasoning_traces=True
  --check      poll run status
  --download   download results, merge reasoning traces into cot_dataset.parquet

Inputs (must already exist):
  datasets_v4/reasoning/for_reasoning.jsonl    (built by build_cot_job.py)
  datasets_v4/reasoning/cot_selection.parquet  (selection with metadata)

Outputs:
  datasets_v4/reasoning/run_metadata.json
  datasets_v4/reasoning/adapted_output.jsonl   (raw Adaption output)
  datasets_v4/reasoning/cot_dataset.parquet    (selection joined with reasoning)
  datasets_v4/reasoning/cot_dataset.csv

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
COT = V4 / "reasoning"

UPLOAD = COT / "for_reasoning.jsonl"
SELECTION = COT / "cot_selection.parquet"
META = COT / "run_metadata.json"
OUTPUT = COT / "adapted_output.jsonl"
DATASET_PARQUET = COT / "cot_dataset.parquet"
DATASET_CSV = COT / "cot_dataset.csv"


def _client():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: ADAPTION_API_KEY not set")
    from adaption import Adaption
    return Adaption(api_key=api_key)


def _check_inputs():
    if not UPLOAD.exists():
        raise SystemExit(f"missing {UPLOAD} — run build_cot_job.py first")
    if not SELECTION.exists():
        raise SystemExit(f"missing {SELECTION} — run build_cot_job.py first")


def _run_kwargs(dataset_id: str, estimate: bool) -> dict:
    return dict(
        dataset_id=dataset_id,
        column_mapping={
            "prompt": "prompt",
            "completion": "completion",
            "context": ["data_uuid", "persona_id", "archetype", "fraud_vector",
                        "typology", "instrument", "amount_usd", "is_fraud", "language"],
        },
        recipe_specification={
            "version": "v1",
            "recipes": {
                "deduplication": False,
                "prompt_rephrase": True,
                "reasoning_traces": True,
                "preference_pairs": False,
                "prompt_metadata_injection": True,
            },
        },
        brand_controls={"length": "detailed", "hallucination_mitigation": False},
        estimate=estimate,
    )


def _row_count(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def do_estimate():
    _check_inputs()
    client = _client()
    up = client.datasets.upload_file(path=str(UPLOAD), name="fraud-v4-cot-3926")
    resp = client.datasets.run(**_run_kwargs(up.dataset_id, estimate=True))
    print(f"rows:       {_row_count(UPLOAD)}")
    print(f"dataset_id: {up.dataset_id}")
    print(f"credits:    {resp.estimated_credits_consumed}")
    print(f"minutes:    {resp.estimated_minutes:.0f}")


def do_submit():
    _check_inputs()
    n = _row_count(UPLOAD)
    client = _client()
    up = client.datasets.upload_file(path=str(UPLOAD), name="fraud-v4-cot-3926")
    resp = client.datasets.run(**_run_kwargs(up.dataset_id, estimate=False))
    META.write_text(json.dumps({
        "dataset_id": up.dataset_id,
        "run_id": resp.run_id,
        "credits": resp.estimated_credits_consumed,
        "estimated_minutes": resp.estimated_minutes,
        "n_rows": n,
        "status": "running",
    }, indent=2), encoding="utf-8")
    print(f"dataset_id: {up.dataset_id}")
    print(f"run_id:     {resp.run_id}")
    print(f"rows:       {n}")
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


def _parse_download(content: str) -> pd.DataFrame:
    """Capture every field Adaption returns; prioritize reasoning-trace columns."""
    records = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Adaption's reasoning recipe typically emits either:
        #   enhanced_completion  — the final answer (verdict + optional reasoning)
        #   reasoning_trace / reasoning / chain_of_thought — the trace
        completion = r.get("enhanced_completion") or r.get("completion") or ""
        if isinstance(completion, dict):
            completion = json.dumps(completion, ensure_ascii=False)
        trace = (r.get("reasoning_trace") or r.get("reasoning")
                 or r.get("chain_of_thought") or r.get("cot") or "")
        if isinstance(trace, dict):
            trace = json.dumps(trace, ensure_ascii=False)
        records.append({
            "data_uuid": r.get("data_uuid", ""),
            "cot_completion": str(completion)[:4000],
            "cot_reasoning_trace": str(trace)[:6000],
            "enhanced_prompt": r.get("enhanced_prompt", ""),
        })
    return pd.DataFrame(records)


def do_download():
    if not META.exists():
        raise SystemExit(f"no {META} — run --submit first")
    meta = json.loads(META.read_text(encoding="utf-8"))
    client = _client()
    st = client.datasets.get_status(meta["dataset_id"])
    if st.status != "succeeded":
        print(f"status={st.status} — not ready")
        return

    # Quality grade
    try:
        ev = client.datasets.get_evaluation(meta["dataset_id"])
        if ev.quality:
            print(f"quality: {ev.quality.grade_before} ({ev.quality.score_before}) -> "
                  f"{ev.quality.grade_after} ({ev.quality.score_after}) "
                  f"| +{ev.quality.improvement_percent}%")
    except Exception:
        pass

    content = client.datasets.download(meta["dataset_id"], file_format="jsonl")
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"downloaded: {OUTPUT}  ({len(content)} bytes)")

    adapted = _parse_download(content)
    selection = pd.read_parquet(SELECTION)
    joined = selection.merge(adapted, on="data_uuid", how="left")

    filled = int((joined["cot_reasoning_trace"].astype(str).str.len() > 0).sum()) \
        if "cot_reasoning_trace" in joined.columns else 0
    completions = int((joined["cot_completion"].astype(str).str.len() > 0).sum()) \
        if "cot_completion" in joined.columns else 0

    joined.to_parquet(DATASET_PARQUET, index=False, engine="pyarrow")
    joined.to_csv(DATASET_CSV, index=False)
    print(f"cot dataset: {DATASET_PARQUET} ({len(joined)} rows)")
    print(f"  with completion:      {completions}/{len(joined)}")
    print(f"  with reasoning trace: {filled}/{len(joined)}")

    # Fraud/legit split of filled traces
    if "cot_reasoning_trace" in joined.columns:
        has_trace = joined[joined["cot_reasoning_trace"].astype(str).str.len() > 0]
        print(f"  fraud with trace:    {int((has_trace['is_fraud']==1).sum())}")
        print(f"  legit with trace:    {int((has_trace['is_fraud']==0).sum())}")

    meta["status"] = "downloaded"
    meta["completions_filled"] = completions
    meta["reasoning_traces_filled"] = filled
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