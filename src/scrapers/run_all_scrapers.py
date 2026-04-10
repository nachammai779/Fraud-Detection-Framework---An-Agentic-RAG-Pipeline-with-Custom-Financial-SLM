"""
run_all_scrapers.py
===================
Master runner — executes all scrapers in sequence and merges
outputs into a single seed_narratives.jsonl per archetype.

No API keys required — all sources are public.

Usage:
    python run_all_scrapers.py
    python run_all_scrapers.py --archetypes remittance gig_worker

After running, each archetype folder will have:
    datasets/{archetype}/raw/seed_narratives_web.jsonl    <- Reddit archive (Pullpush)
    datasets/{archetype}/raw/seed_narratives_cfpb.jsonl   <- CFPB complaints
    datasets/{archetype}/raw/seed_narratives_bbb.jsonl    <- BBB Scam Tracker
    datasets/{archetype}/raw/seed_narratives.jsonl        <- MERGED (use this)
    datasets/{archetype}/raw/scrape_summary.json          <- Stats

Language distribution in merged output:
    - English:        CFPB + English Reddit/BBB posts
    - Spanish:        Reddit Spanish-language posts
    - Hinglish:       Reddit r/AbcDesis, r/india posts
    - Haitian Creole: Reddit Haiti-focused posts
    - Yoruba/Twi:     Reddit Nigeria/Ghana posts
    - Tamil:          Reddit Tamil community posts
"""

import json
import os
import argparse
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.dirname(__file__))

from web_scraper import run_all as run_web
from cfpb_scraper import run_all_cfpb
from bbb_scraper import run_all as run_bbb


ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def merge_archetype_sources(archetype_name, output_dir="datasets"):
    """Merge all source JSONL files for one archetype into single file."""
    raw_dir = os.path.join(output_dir, archetype_name, "raw")
    merged = []
    seen_narratives = set()

    source_files = [
        "seed_narratives_web.jsonl",
        "seed_narratives_cfpb.jsonl",
        "seed_narratives_bbb.jsonl",
    ]

    for fname in source_files:
        fpath = os.path.join(raw_dir, fname)
        if not os.path.exists(fpath):
            print(f"  Warning: {fname} not found — skipping")
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line.strip())
                # Deduplicate by narrative content fingerprint
                fingerprint = record.get("narrative_text", "")[:100]
                if fingerprint in seen_narratives:
                    continue
                seen_narratives.add(fingerprint)
                merged.append(record)

    # Save merged
    merged_path = os.path.join(raw_dir, "seed_narratives.jsonl")
    with open(merged_path, "w", encoding="utf-8") as f:
        for record in merged:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Language breakdown
    lang_counts = {}
    vector_counts = {}
    for r in merged:
        for lang in r.get("detected_language_hints", ["en"]):
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        vector = r.get("fraud_vector_hint", "unknown")
        vector_counts[vector] = vector_counts.get(vector, 0) + 1

    # Source breakdown
    source_counts = {}
    for r in merged:
        src = r.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    summary = {
        "archetype": archetype_name,
        "total_records": len(merged),
        "sources": source_counts,
        "language_distribution": lang_counts,
        "fraud_vector_distribution": vector_counts,
        "merged_at": datetime.now(timezone.utc).isoformat(),
        "output_file": merged_path,
        "ready_for_adaptive_data": len(merged) >= 30,
        "ready_for_tabddpm": len(merged) >= 50,
    }

    summary_path = os.path.join(raw_dir, "scrape_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def print_final_report(summaries):
    """Print final cross-archetype summary."""
    print(f"\n{'='*70}")
    print("FINAL SCRAPE REPORT — All Archetypes")
    print(f"{'='*70}")
    print(f"{'Archetype':<20} {'Total':<8} {'Languages':<30} {'Ready?'}")
    print("-" * 70)

    for s in summaries:
        langs = ", ".join(s["language_distribution"].keys())
        ready = "YES" if s["ready_for_adaptive_data"] else "Need more"
        print(f"{s['archetype']:<20} {s['total_records']:<8} {langs:<30} {ready}")

    print(f"\n{'='*70}")
    print("Next steps:")
    print("  1. Upload seed_narratives.jsonl files to Adaptive Data for reshaping")
    print("  2. Run narrative_generator.py to expand to 75-100 per archetype")
    print("  3. Run tabddpm_generator.py using behavioral profiles")
    print(f"{'='*70}")


def run_all(output_dir="datasets", archetypes=None):
    targets = archetypes or ARCHETYPES

    print("=" * 70)
    print("UNDERSERVED FRAUD DATASET — Master Scraper")
    print("No API keys required — all sources are public")
    print("=" * 70)
    print(f"Archetypes: {targets}")
    print(f"Output: {output_dir}/\n")

    # Step 1: Web scraper (Reddit archive via Pullpush)
    print("\n>>> STEP 1: Web Scraper (Pullpush.io — Reddit archive)")
    run_web(output_dir=output_dir, archetypes_to_run=targets)

    # Step 2: CFPB
    print("\n>>> STEP 2: CFPB Scraper")
    run_all_cfpb(output_dir=output_dir, archetypes_to_run=targets)

    # Step 3: BBB Scam Tracker
    print("\n>>> STEP 3: BBB Scam Tracker")
    run_bbb(output_dir=output_dir, archetypes_to_run=targets)

    # Step 4: Merge
    print("\n>>> STEP 4: Merging Sources")
    summaries = []
    for archetype in targets:
        print(f"\n  Merging: {archetype}")
        summary = merge_archetype_sources(archetype, output_dir=output_dir)
        summaries.append(summary)
        print(f"  -> {summary['total_records']} total records")
        print(f"  -> Languages: {summary['language_distribution']}")

    print_final_report(summaries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Master scraper runner — no API keys needed"
    )
    parser.add_argument("--output_dir", default="datasets",
                        help="Root output directory")
    parser.add_argument("--archetypes", nargs="+", choices=ARCHETYPES,
                        help="Archetypes to run (default: all 4)")
    args = parser.parse_args()

    run_all(output_dir=args.output_dir, archetypes=args.archetypes)