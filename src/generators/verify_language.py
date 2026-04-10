"""
verify_language.py
==================
Verifies that Adaption-generated narratives match the expected
language from the profile config using langdetect.

Reads adapted_output.jsonl, detects language of each enhanced_completion,
compares against the 'language' field, and reports mismatches.

Usage:
    python verify_language.py --archetype remittance
    python verify_language.py --all
"""

import os
import sys
import json
import argparse
from collections import Counter

from langdetect import detect, DetectorFactory

# Deterministic detection
DetectorFactory.seed = 0

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "scrapers"))

from profile_configs import PROFILES

# Map our language codes to langdetect codes
# langdetect uses ISO 639-1; our codes mostly match except a few
LANG_MAP = {
    "en": ["en"],
    "es": ["es"],
    "hi": ["hi", "mr"],         # Hinglish may detect as Hindi or Marathi
    "ta": ["ta"],
    "ta-en": ["en", "ta"],      # Tanglish can detect as either
    "ht": ["fr", "ht"],         # Haitian Creole often detected as French
    "yo": ["yo", "en", "so"],   # Yoruba detection is weak, may fall back to English/Somali
    "vi": ["vi"],
}


def find_adapted_output(archetype):
    """Locate adapted_output.jsonl for an archetype."""
    candidates = [
        os.path.join(PROJECT_ROOT, "datasets", archetype, "adaptive", "adapted_output.jsonl"),
        os.path.join(PROJECT_ROOT, "src", "scrapers", "datasets", archetype, "adaptive", "adapted_output.jsonl"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"No adapted_output.jsonl found for {archetype}")


def detect_language(text):
    """Detect language of text. Returns ISO 639-1 code or 'unknown'."""
    if not text or len(text.strip()) < 20:
        return "unknown"
    try:
        return detect(text)
    except Exception:
        return "unknown"


def verify_archetype(archetype):
    """Verify language alignment for one archetype's adapted output."""
    print(f"\n{'='*60}")
    print(f"Language Verification: {archetype.upper()}")
    print(f"{'='*60}")

    path = find_adapted_output(archetype)
    print(f"  Source: {path}")

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line.strip()))

    print(f"  Records: {len(records)}")

    results = []
    for r in records:
        narrative = r.get("enhanced_completion", "")
        expected_lang = r.get("language", "en")
        detected_lang = detect_language(narrative)

        # Check if detected language is acceptable for expected code
        acceptable = LANG_MAP.get(expected_lang, [expected_lang])
        match = detected_lang in acceptable

        results.append({
            "data_uuid": r.get("data_uuid", ""),
            "expected": expected_lang,
            "detected": detected_lang,
            "match": match,
            "narrative_preview": narrative[:80],
        })

    # Summary stats
    total = len(results)
    matched = sum(1 for r in results if r["match"])
    mismatched = total - matched

    print(f"\n  RESULTS:")
    print(f"    Total:     {total}")
    print(f"    Matched:   {matched} ({100*matched/max(total,1):.0f}%)")
    print(f"    Mismatch:  {mismatched} ({100*mismatched/max(total,1):.0f}%)")

    # Breakdown by expected language
    expected_counts = Counter(r["expected"] for r in results)
    print(f"\n  BY EXPECTED LANGUAGE:")
    print(f"    {'Expected':<12} {'Count':<8} {'Matched':<10} {'Detected as'}")
    print(f"    {'-'*55}")

    for lang in sorted(expected_counts.keys()):
        lang_results = [r for r in results if r["expected"] == lang]
        lang_matched = sum(1 for r in lang_results if r["match"])
        detected_dist = Counter(r["detected"] for r in lang_results)
        detected_str = ", ".join(f"{k}:{v}" for k, v in detected_dist.most_common())
        print(f"    {lang:<12} {len(lang_results):<8} {lang_matched}/{len(lang_results):<8} {detected_str}")

    # Show mismatches
    mismatches = [r for r in results if not r["match"]]
    if mismatches:
        print(f"\n  MISMATCHES ({len(mismatches)}):")
        for r in mismatches[:10]:
            preview = r['narrative_preview'].encode('ascii', 'replace').decode()
            print(f"    [{r['expected']} -> {r['detected']}] {preview}...")
        if len(mismatches) > 10:
            print(f"    ... and {len(mismatches) - 10} more")

    return {
        "archetype": archetype,
        "total": total,
        "matched": matched,
        "mismatched": mismatched,
        "match_rate": matched / max(total, 1),
        "by_language": {
            lang: {
                "count": len([r for r in results if r["expected"] == lang]),
                "matched": sum(1 for r in results if r["expected"] == lang and r["match"]),
            }
            for lang in expected_counts
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify language of adapted narratives")
    parser.add_argument("--archetype", choices=list(PROFILES.keys()))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if not args.archetype and not args.all:
        parser.error("Specify --archetype <name> or --all")

    targets = list(PROFILES.keys()) if args.all else [args.archetype]

    all_results = []
    for arch in targets:
        try:
            result = verify_archetype(arch)
            all_results.append(result)
        except FileNotFoundError as e:
            print(f"\n  SKIP: {e}")

    if all_results:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for r in all_results:
            print(f"  {r['archetype']}: {r['matched']}/{r['total']} matched ({r['match_rate']:.0%})")
