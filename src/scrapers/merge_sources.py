"""
merge_sources.py
================
Merges all scraped JSONL files into a single seed_narratives.jsonl
per archetype and generates scrape_summary.json with stats.

Looks for these source files in each archetype's raw/ folder:
    - seed_narratives_web.jsonl    (Pullpush / Reddit archive)
    - seed_narratives_cfpb.jsonl   (CFPB complaints)
    - seed_narratives_bbb.jsonl    (BBB Scam Tracker)

Usage:
    python merge_sources.py
    python merge_sources.py --archetypes remittance gig_worker
    python merge_sources.py --output_dir ../../datasets
"""

import json
import os
import argparse
from datetime import datetime, timezone

ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]

SOURCE_FILES = [
    "seed_narratives_web.jsonl",
    "seed_narratives_cfpb.jsonl",
    "seed_narratives_bbb.jsonl",
]


def merge_archetype(archetype_name, output_dir="datasets"):
    """Merge all source JSONL files for one archetype."""
    raw_dir = os.path.join(output_dir, archetype_name, "raw")

    if not os.path.isdir(raw_dir):
        print(f"  SKIP -- {raw_dir} does not exist")
        return None

    merged = []
    seen_narratives = set()
    files_found = {}

    for fname in SOURCE_FILES:
        fpath = os.path.join(raw_dir, fname)
        if not os.path.exists(fpath):
            print(f"  Warning: {fname} not found -- skipping")
            files_found[fname] = 0
            continue

        count = 0
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                # Deduplicate by first 100 chars of narrative
                fingerprint = record.get("narrative_text", "")[:100]
                if fingerprint in seen_narratives:
                    continue
                seen_narratives.add(fingerprint)
                merged.append(record)
                count += 1

        files_found[fname] = count
        print(f"  {fname}: {count} records")

    # Save merged JSONL
    merged_path = os.path.join(raw_dir, "seed_narratives.jsonl")
    with open(merged_path, "w", encoding="utf-8") as f:
        for record in merged:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Compute stats
    lang_counts = {}
    vector_counts = {}
    source_counts = {}
    for r in merged:
        for lang in r.get("detected_language_hints", ["en"]):
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        vector = r.get("fraud_vector_hint", "unknown")
        vector_counts[vector] = vector_counts.get(vector, 0) + 1
        src = r.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    summary = {
        "archetype": archetype_name,
        "total_records": len(merged),
        "source_files": files_found,
        "source_distribution": source_counts,
        "language_distribution": lang_counts,
        "fraud_vector_distribution": vector_counts,
        "merged_at": datetime.now(timezone.utc).isoformat(),
        "output_file": merged_path,
        "ready_for_adaptive_data": len(merged) >= 30,
        "ready_for_tabddpm": len(merged) >= 50,
    }

    summary_path = os.path.join(raw_dir, "scrape_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary


def print_report(summaries):
    """Print final cross-archetype report."""
    print(f"\n{'='*70}")
    print("MERGE REPORT")
    print(f"{'='*70}")
    print(f"{'Archetype':<15} {'Total':<8} {'Sources':<35} {'Languages':<20} {'Ready?'}")
    print("-" * 70)

    for s in summaries:
        sources = ", ".join(f"{k}:{v}" for k, v in s["source_distribution"].items())
        langs = ", ".join(s["language_distribution"].keys())
        ready = "YES" if s["ready_for_adaptive_data"] else "NEED MORE"
        print(f"{s['archetype']:<15} {s['total_records']:<8} {sources:<35} {langs:<20} {ready}")

    total = sum(s["total_records"] for s in summaries)
    print(f"\nTotal across all archetypes: {total} records")
    print(f"{'='*70}")


def run(output_dir="datasets", archetypes=None):
    targets = archetypes or ARCHETYPES

    print("Merging scraped sources into seed_narratives.jsonl")
    print(f"Output dir: {output_dir}")
    print(f"Archetypes: {targets}\n")

    summaries = []
    for name in targets:
        print(f"\n--- {name.upper()} ---")
        summary = merge_archetype(name, output_dir=output_dir)
        if summary:
            summaries.append(summary)
            print(f"  -> Merged: {summary['total_records']} records -> seed_narratives.jsonl")

    if summaries:
        print_report(summaries)
    else:
        print("\nNo data found to merge.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge all scraped JSONL sources per archetype")
    parser.add_argument("--output_dir", default="datasets",
                        help="Root output directory (default: datasets/)")
    parser.add_argument("--archetypes", nargs="+", choices=ARCHETYPES,
                        help="Which archetypes to merge (default: all 4)")
    args = parser.parse_args()

    run(output_dir=args.output_dir, archetypes=args.archetypes)