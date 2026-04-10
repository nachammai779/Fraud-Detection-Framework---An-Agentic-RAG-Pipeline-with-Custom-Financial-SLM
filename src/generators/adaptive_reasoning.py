"""
adaptive_reasoning.py
=====================
Submits 100 sampled rows per archetype to Adaption Labs with
reasoning_traces enabled. This adds chain-of-thought reasoning
to the generated narratives.

Usage:
    # Estimate credits first
    python adaptive_reasoning.py --estimate

    # Submit all 4
    python adaptive_reasoning.py --submit

    # Check status
    python adaptive_reasoning.py --check

    # Download results
    python adaptive_reasoning.py --download
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

TRACKER_PATH = os.path.join(PROJECT_ROOT, "datasets", "adaption_reasoning_jobs.json")
SAMPLE_SIZE = 100


def find_parquet(archetype):
    candidates = [
        os.path.join(PROJECT_ROOT, "notebooks", "generation", "tabddpm_output", archetype, "transactions.parquet"),
        os.path.join(PROJECT_ROOT, "datasets", archetype, "synthetic", "transactions.parquet"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def format_for_adaption(df, archetype, profile):
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


def estimate_all():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return

    client = Adaption(api_key=api_key)

    for arch in PROFILES:
        print(f"\n{'='*50}")
        print(f"  {arch.upper()} (sampling {SAMPLE_SIZE} rows)")
        print(f"{'='*50}")

        pq = find_parquet(arch)
        if not pq:
            print(f"  SKIP: no parquet found")
            continue

        df = pd.read_parquet(pq).sample(n=SAMPLE_SIZE, random_state=42)
        df_upload = format_for_adaption(df, arch, PROFILES[arch])

        out_dir = os.path.join(PROJECT_ROOT, "datasets", arch, "reasoning")
        os.makedirs(out_dir, exist_ok=True)
        upload_path = os.path.join(out_dir, "for_reasoning.jsonl")
        df_upload.to_json(upload_path, orient="records", lines=True, force_ascii=False)

        upload_resp = client.datasets.upload_file(
            path=upload_path,
            name=f"fraud-{arch}-reasoning-{SAMPLE_SIZE}rows",
        )

        resp = client.datasets.run(
            dataset_id=upload_resp.dataset_id,
            column_mapping={
                "prompt": "prompt",
                "completion": "completion",
                "context": ["archetype", "fraud_vector", "language", "instrument", "amount_usd", "is_fraud"],
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
            brand_controls={
                "length": "detailed",
                "hallucination_mitigation": False,
            },
            estimate=True,
        )
        print(f"  Dataset ID: {upload_resp.dataset_id}")
        print(f"  Credits:    {resp.estimated_credits_consumed}")
        print(f"  Time:       {resp.estimated_minutes:.0f} min")


def submit_all():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return

    client = Adaption(api_key=api_key)
    tracker = {}

    for arch in PROFILES:
        print(f"\n{'='*50}")
        print(f"  {arch.upper()} (sampling {SAMPLE_SIZE} rows)")
        print(f"{'='*50}")

        pq = find_parquet(arch)
        if not pq:
            print(f"  SKIP: no parquet found")
            continue

        df = pd.read_parquet(pq).sample(n=SAMPLE_SIZE, random_state=42)
        df_upload = format_for_adaption(df, arch, PROFILES[arch])

        out_dir = os.path.join(PROJECT_ROOT, "datasets", arch, "reasoning")
        os.makedirs(out_dir, exist_ok=True)
        upload_path = os.path.join(out_dir, "for_reasoning.jsonl")
        df_upload.to_json(upload_path, orient="records", lines=True, force_ascii=False)

        print(f"  Uploading {len(df_upload)} rows...")
        upload_resp = client.datasets.upload_file(
            path=upload_path,
            name=f"fraud-{arch}-reasoning-{SAMPLE_SIZE}rows",
        )
        dataset_id = upload_resp.dataset_id

        print(f"  Submitting with reasoning_traces=True...")
        resp = client.datasets.run(
            dataset_id=dataset_id,
            column_mapping={
                "prompt": "prompt",
                "completion": "completion",
                "context": ["archetype", "fraud_vector", "language", "instrument", "amount_usd", "is_fraud"],
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
            brand_controls={
                "length": "detailed",
                "hallucination_mitigation": False,
            },
            estimate=False,
        )

        tracker[arch] = {
            "dataset_id": dataset_id,
            "run_id": resp.run_id,
            "credits": resp.estimated_credits_consumed,
            "estimated_minutes": resp.estimated_minutes,
            "rows": len(df_upload),
            "status": "running",
        }
        print(f"  Run ID:  {resp.run_id}")
        print(f"  Credits: {resp.estimated_credits_consumed}")
        print(f"  ETA:     {resp.estimated_minutes:.0f} min")

    with open(TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2)
    print(f"\nTracker saved: {TRACKER_PATH}")
    print("Check status: python src/generators/adaptive_reasoning.py --check")


def check_all():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return

    if not os.path.exists(TRACKER_PATH):
        print("No tracker found. Run --submit first.")
        return

    with open(TRACKER_PATH, "r") as f:
        tracker = json.load(f)

    client = Adaption(api_key=api_key)

    print(f"{'Archetype':<15} {'Status':<12} {'Progress':<20}")
    print("-" * 50)

    all_done = True
    for arch, info in tracker.items():
        status = client.datasets.get_status(info["dataset_id"])
        s = status.status
        progress = ""
        if status.progress:
            p = status.progress
            progress = f"{p.processed_rows}/{p.total_rows}"
        print(f"  {arch:<13} {s:<12} {progress}")
        tracker[arch]["status"] = s
        if s not in ("succeeded", "failed"):
            all_done = False

    with open(TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2)

    if all_done:
        print("\nAll done. Run: python src/generators/adaptive_reasoning.py --download")


def download_all():
    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ERROR: ADAPTION_API_KEY not set")
        return

    if not os.path.exists(TRACKER_PATH):
        print("No tracker found. Run --submit first.")
        return

    with open(TRACKER_PATH, "r") as f:
        tracker = json.load(f)

    client = Adaption(api_key=api_key)

    for arch, info in tracker.items():
        print(f"\n{'='*50}")
        print(f"  {arch.upper()}")
        print(f"{'='*50}")

        status = client.datasets.get_status(info["dataset_id"])
        if status.status != "succeeded":
            print(f"  Status: {status.status} -- skipping")
            continue

        # Evaluation
        try:
            ev = client.datasets.get_evaluation(info["dataset_id"])
            if ev.quality:
                print(f"  Quality: {ev.quality.grade_before} ({ev.quality.score_before}) -> {ev.quality.grade_after} ({ev.quality.score_after}) | +{ev.quality.improvement_percent}%")
        except Exception:
            pass

        # Download
        result = client.datasets.download(info["dataset_id"], file_format="jsonl")

        out_dir = os.path.join(PROJECT_ROOT, "datasets", arch, "reasoning")
        os.makedirs(out_dir, exist_ok=True)

        raw_path = os.path.join(out_dir, "reasoning_output.jsonl")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(result)

        records = [json.loads(line) for line in result.strip().split("\n") if line.strip()]
        print(f"  Downloaded: {len(records)} records")
        print(f"  Columns: {list(records[0].keys()) if records else 'N/A'}")

        # Save CSV for viewing
        df_out = pd.DataFrame(records)
        csv_path = os.path.join(out_dir, f"reasoning_{arch}.csv")
        df_out.to_csv(csv_path, index=False)
        print(f"  CSV: {csv_path}")

        # Show a sample
        if records:
            r = records[0]
            print(f"\n  SAMPLE RECORD:")
            for col in r:
                val = str(r[col])[:120]
                print(f"    {col}: {val}")

        tracker[arch]["status"] = "downloaded"
        tracker[arch]["records"] = len(records)

    with open(TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reasoning traces via Adaption Labs")
    parser.add_argument("--estimate", action="store_true", help="Estimate credits")
    parser.add_argument("--submit", action="store_true", help="Submit all 4 jobs")
    parser.add_argument("--check", action="store_true", help="Check job status")
    parser.add_argument("--download", action="store_true", help="Download results")
    args = parser.parse_args()

    if not any([args.estimate, args.submit, args.check, args.download]):
        parser.error("Specify --estimate, --submit, --check, or --download")

    if args.estimate:
        estimate_all()
    elif args.submit:
        submit_all()
    elif args.check:
        check_all()
    elif args.download:
        download_all()
