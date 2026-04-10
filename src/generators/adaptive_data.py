"""
adaptive_data.py
================
Fills empty narrative_text in TabDDPM synthetic transactions using
Adaption Labs API. Each row's fraud_vector, language, instrument,
and amount become the prompt context for narrative generation.

Input:  TabDDPM parquet (5,000 rows with empty narrative_text)
Output: Same structure with narrative_text filled by Adaption

Prerequisites:
    pip install adaption
    export ADAPTION_API_KEY=sk-...   (or set on Windows)

Usage:
    # Estimate credits first (free, no charge)
    python adaptive_data.py --archetype remittance --estimate

    # Estimate with row limit
    python adaptive_data.py --archetype remittance --estimate --max_rows 50

    # Full run
    python adaptive_data.py --archetype remittance

    # Full run, limited rows (controls cost)
    python adaptive_data.py --archetype remittance --max_rows 100
"""

import os
import sys
import json
import argparse
import pandas as pd

from adaption import Adaption

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "scrapers"))

from profile_configs import PROFILES


# ── Locate TabDDPM parquet ───────────────────────────────────────────────────

def find_parquet(archetype):
    """Find the TabDDPM parquet for an archetype. Checks Colab output first."""
    candidates = [
        os.path.join(PROJECT_ROOT, "notebooks", "generation", "tabddpm_output", archetype, "transactions.parquet"),
        os.path.join(PROJECT_ROOT, "datasets", archetype, "synthetic", "transactions.parquet"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"No transactions.parquet found for {archetype}. Looked in:\n  " + "\n  ".join(candidates)
    )


# ── Format TabDDPM rows as prompt/completion for Adaption ────────────────────

def format_parquet_for_adaption(df, archetype, profile):
    """Convert TabDDPM synthetic rows into prompt/completion pairs.

    Each row becomes:
        prompt:     Rich context from the row's transaction fields
        completion: Empty string (Adaption will generate this)
        context:    Metadata columns for Adaption to use
    """
    rows = []
    for _, r in df.iterrows():
        fraud_vector = r.get("fraud_vector", r.get("fraud_vector_hint", "unknown"))
        language = r.get("language", "en")
        instrument = r.get("instrument", "unknown")
        amount = r.get("transaction_amount_usd", 0)
        is_fraud = int(r.get("is_fraud", 0))
        age = int(r.get("sender_age", 30))

        fraud_label = "fraudulent" if is_fraud else "legitimate"

        prompt = (
            f"Write a first-person narrative from a victim or participant in a {fraud_label} "
            f"financial transaction. Archetype: {archetype}. "
            f"Fraud vector: {fraud_vector}. "
            f"Financial instrument: {instrument}. "
            f"Transaction amount: ${amount:.2f}. "
            f"Sender age: {age}. "
            f"Language: {language}. "
            f"Community context: {profile['description']}. "
            f"Write 3-5 sentences describing what happened, how the scam worked "
            f"(or how the legitimate transaction proceeded), the financial impact, "
            f"and the person's emotional response. Use natural language appropriate "
            f"for the specified language code."
        )

        # Completion is empty — Adaption generates it
        rows.append({
            "prompt": prompt,
            "completion": "",
            "data_uuid": r.get("data_uuid", ""),
            "archetype": archetype,
            "fraud_vector": str(fraud_vector),
            "language": str(language),
            "instrument": str(instrument),
            "amount_usd": float(amount),
            "is_fraud": int(is_fraud),
        })

    return pd.DataFrame(rows)


# ── Adaption API workflow ────────────────────────────────────────────────────

def run_adaptation(
    archetype,
    estimate_only=False,
    max_rows=None,
    output_dir="datasets",
):
    """Full Adaption Labs pipeline for one archetype."""
    print(f"\n{'='*60}")
    print(f"Adaptive Data: {archetype.upper()}")
    print(f"{'='*60}")

    profile = PROFILES[archetype]

    # Step 1: Load TabDDPM parquet
    print("\n  [1/5] Loading TabDDPM synthetic transactions...")
    parquet_path = find_parquet(archetype)
    df_full = pd.read_parquet(parquet_path)
    print(f"    Source: {parquet_path}")
    print(f"    Total rows: {len(df_full)}")
    print(f"    narrative_text empty: {(df_full['narrative_text'] == '').all()}")

    # Apply row limit if set
    df_input = df_full.head(max_rows) if max_rows else df_full
    print(f"    Rows for adaptation: {len(df_input)}")

    # Step 2: Format as prompt/completion
    print("\n  [2/5] Formatting for Adaption API...")
    df_upload = format_parquet_for_adaption(df_input, archetype, profile)
    print(f"    Prompt/completion pairs: {len(df_upload)}")
    print(f"    Fraud vectors: {df_upload['fraud_vector'].nunique()}")
    print(f"    Languages: {df_upload['language'].value_counts().to_dict()}")
    print(f"    Fraud rate: {df_upload['is_fraud'].mean():.1%}")

    # Save JSONL for upload
    adaptive_dir = os.path.join(PROJECT_ROOT, output_dir, archetype, "adaptive")
    os.makedirs(adaptive_dir, exist_ok=True)
    upload_path = os.path.join(adaptive_dir, "for_adaption.jsonl")
    df_upload.to_json(upload_path, orient="records", lines=True, force_ascii=False)
    print(f"    Upload file: {upload_path}")

    # Step 3: Initialize client
    print("\n  [3/5] Connecting to Adaption Labs API...")
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("    WARNING: ADAPTION_API_KEY not set.")
        print("    Set with: export ADAPTION_API_KEY=sk-...")
        print("    Or Windows: set ADAPTION_API_KEY=sk-...")
        print(f"\n    Upload file ready at: {upload_path}")
        print("    You can upload manually at https://app.adaptionlabs.ai")
        return {
            "archetype": archetype,
            "rows": len(df_upload),
            "upload_path": upload_path,
            "mode": "no_api_key",
        }

    client = Adaption(api_key=api_key)
    print("    Connected.")

    # Step 4: Upload
    print("\n  [4/5] Uploading to Adaption Labs...")
    upload_resp = client.datasets.upload_file(
        path=upload_path,
        name=f"fraud-{archetype}-tabddpm-{len(df_upload)}rows",
    )
    dataset_id = upload_resp.dataset_id
    print(f"    Dataset ID: {dataset_id}")

    # Step 5: Configure and run (or estimate)
    column_mapping = {
        "prompt": "prompt",
        "completion": "completion",
        "context": ["archetype", "fraud_vector", "language", "instrument", "amount_usd", "is_fraud"],
    }

    recipe_spec = {
        "version": "v1",
        "recipes": {
            "deduplication": True,
            "prompt_rephrase": True,
            "reasoning_traces": False,
            "preference_pairs": False,
            "prompt_metadata_injection": True,
        },
    }

    brand_controls = {
        "length": "detailed",
        "hallucination_mitigation": False,
    }

    job_spec = {}
    if max_rows:
        job_spec["max_rows"] = max_rows

    if estimate_only:
        print("\n  [5/5] Estimating credits (dry run -- no charge)...")
        resp = client.datasets.run(
            dataset_id=dataset_id,
            column_mapping=column_mapping,
            recipe_specification=recipe_spec,
            brand_controls=brand_controls,
            job_specification=job_spec,
            estimate=True,
        )
        print(f"\n  {'='*40}")
        print(f"  CREDIT ESTIMATE")
        print(f"  {'='*40}")
        print(f"    Rows:             {len(df_upload)}")
        print(f"    Credits required: {resp.estimated_credits_consumed}")
        print(f"    Estimated time:   {resp.estimated_minutes:.1f} minutes")
        print(f"    Run ID:           {resp.run_id or 'N/A (estimate only)'}")
        print(f"    Dataset ID:       {dataset_id}")
        print(f"  {'='*40}")
        return {
            "archetype": archetype,
            "dataset_id": dataset_id,
            "estimated_credits": resp.estimated_credits_consumed,
            "estimated_minutes": resp.estimated_minutes,
            "rows": len(df_upload),
            "mode": "estimate",
        }

    # Full run
    print("\n  [5/5] Starting adaptation run...")
    resp = client.datasets.run(
        dataset_id=dataset_id,
        column_mapping=column_mapping,
        recipe_specification=recipe_spec,
        brand_controls=brand_controls,
        job_specification=job_spec,
        estimate=False,
    )
    run_id = resp.run_id
    print(f"    Run ID:           {run_id}")
    print(f"    Credits reserved: {resp.estimated_credits_consumed}")
    print(f"    Estimated time:   {resp.estimated_minutes:.1f} minutes")

    # Wait for completion
    print("\n    Waiting for completion (polling)...")
    client.datasets.wait_for_completion(dataset_id, timeout=3600.0)
    print("    Adaptation complete.")

    # Get evaluation
    eval_resp = client.datasets.get_evaluation(dataset_id)
    if eval_resp.quality:
        print(f"\n  QUALITY EVALUATION:")
        print(f"    Grade before: {eval_resp.quality.grade_before}")
        print(f"    Grade after:  {eval_resp.quality.grade_after}")
        print(f"    Score before: {eval_resp.quality.score_before}/10")
        print(f"    Score after:  {eval_resp.quality.score_after}/10")
        print(f"    Improvement:  {eval_resp.quality.improvement_percent}%")

    # Download adapted data (SDK returns JSONL content as string, not a URL)
    print(f"\n  Downloading adapted data...")
    result = client.datasets.download(dataset_id, file_format="jsonl")

    adapted_path = os.path.join(adaptive_dir, "adapted_output.jsonl")
    with open(adapted_path, "w", encoding="utf-8") as f:
        f.write(result)

    # Parse
    adapted_records = []
    for line in result.strip().split("\n"):
        if line.strip():
            adapted_records.append(json.loads(line.strip()))

    print(f"    Downloaded: {len(adapted_records)} adapted records")
    print(f"    Saved: {adapted_path}")

    # Merge narratives back into original parquet
    print("\n  Merging narratives back into transactions...")
    df_adapted = pd.DataFrame(adapted_records)

    # Adaption returns enhanced_completion (the generated narrative)
    narrative_col = "enhanced_completion" if "enhanced_completion" in df_adapted.columns else "completion"

    if narrative_col in df_adapted.columns and "data_uuid" in df_adapted.columns:
        narrative_map = dict(zip(df_adapted["data_uuid"], df_adapted[narrative_col]))
        filled = 0
        for idx, row in df_input.iterrows():
            uid = row.get("data_uuid", "")
            if uid in narrative_map and narrative_map[uid]:
                df_full.at[idx, "narrative_text"] = str(narrative_map[uid])[:2000]
                filled += 1
        print(f"    Filled {filled}/{len(df_input)} narrative_text fields (from '{narrative_col}')")
    else:
        print(f"    WARNING: Could not merge. Columns found: {list(df_adapted.columns)}")

    # Save merged output
    merged_parquet = os.path.join(adaptive_dir, "transactions_adapted.parquet")
    df_full.to_parquet(merged_parquet, index=False, engine="pyarrow")

    merged_csv = os.path.join(adaptive_dir, f"transactions_adapted_{archetype}.csv")
    df_full.to_csv(merged_csv, index=False)

    print(f"    Parquet: {merged_parquet}")
    print(f"    CSV:     {merged_csv}")

    return {
        "archetype": archetype,
        "dataset_id": dataset_id,
        "run_id": run_id,
        "credits_consumed": resp.estimated_credits_consumed,
        "input_rows": len(df_input),
        "adapted_rows": len(adapted_records),
        "output_parquet": merged_parquet,
        "output_csv": merged_csv,
        "mode": "full_run",
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fill TabDDPM synthetic narratives via Adaption Labs API"
    )
    parser.add_argument("--archetype", choices=list(PROFILES.keys()),
                        help="Single archetype to adapt")
    parser.add_argument("--all", action="store_true",
                        help="Run all 4 archetypes")
    parser.add_argument("--estimate", action="store_true",
                        help="Estimate credits only (no run, no charge)")
    parser.add_argument("--max_rows", type=int, default=None,
                        help="Limit rows to process (controls cost)")
    parser.add_argument("--output_dir", default="datasets")
    args = parser.parse_args()

    if not args.archetype and not args.all:
        parser.error("Specify --archetype <name> or --all")

    targets = list(PROFILES.keys()) if args.all else [args.archetype]

    results = []
    for arch in targets:
        result = run_adaptation(
            arch,
            estimate_only=args.estimate,
            max_rows=args.max_rows,
            output_dir=args.output_dir,
        )
        if result:
            results.append(result)

    if results:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for r in results:
            if r["mode"] == "estimate":
                print(f"  {r['archetype']}: {r['rows']} rows -> ~{r['estimated_credits']} credits, ~{r['estimated_minutes']:.0f} min")
            elif r["mode"] == "no_api_key":
                print(f"  {r['archetype']}: {r['rows']} rows prepared -> {r['upload_path']}")
            else:
                print(f"  {r['archetype']}: {r['input_rows']} -> {r['adapted_rows']} rows, {r['credits_consumed']} credits")
                print(f"    Output: {r['output_parquet']}")
