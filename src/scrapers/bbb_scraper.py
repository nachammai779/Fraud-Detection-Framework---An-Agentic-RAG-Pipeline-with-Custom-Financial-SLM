"""
bbb_scraper.py
==============
Scrapes BBB Scam Tracker for fraud seed narratives.
No API key required — parses server-rendered search pages.

BBB moved to Next.js RSC (no public API), so this scraper fetches
the search page HTML and extracts Elasticsearch results from the
embedded React Server Component flight data.

Usage:
    python bbb_scraper.py
    python bbb_scraper.py --archetypes remittance gig_worker
"""

import requests
import json
import re
import time
import argparse
import os
from datetime import datetime, timezone
from urllib.parse import quote

# ── Archetype → BBB search config ────────────────────────────────────────────

ARCHETYPES = {
    "remittance": {
        "queries": [
            {"all": "wire transfer scam"},
            {"all": "money transfer fraud"},
            {"all": "Western Union scam"},
            {"all": "MoneyGram fraud"},
            {"all": "remittance scam"},
            {"scam_type": "Foreign Money Exchange"},
        ],
        "fraud_vector_hints": [
            "interception", "emergency", "exchange rate", "bonus",
            "fake family", "wire transfer", "MoneyGram", "Western Union",
        ],
    },
    "gig_worker": {
        "queries": [
            {"all": "account takeover driver"},
            {"all": "CashApp scam"},
            {"all": "Venmo fraud"},
            {"all": "Zelle scam"},
            {"all": "gig worker scam"},
            {"all": "PayPal account hacked"},
        ],
        "fraud_vector_hints": [
            "account takeover", "ATO", "SIM swap", "OTP",
            "social engineering", "fake support", "hacked", "stolen",
        ],
    },
    "unbanked": {
        "queries": [
            {"all": "prepaid card scam"},
            {"all": "payday loan fraud"},
            {"all": "cash advance scam"},
            {"all": "advance fee loan"},
            {"scam_type": "Advance Fee Loan"},
            {"scam_type": "Credit Repair/Debt Relief"},
        ],
        "fraud_vector_hints": [
            "load fee", "advance fee", "predatory", "fake loan",
            "kiosk", "prepaid", "payday",
        ],
    },
    "itin": {
        "queries": [
            {"all": "identity theft immigrant"},
            {"all": "tax fraud identity"},
            {"all": "synthetic identity"},
            {"all": "immigration consultant scam"},
            {"scam_type": "Identity Theft"},
            {"scam_type": "Tax Collection"},
        ],
        "fraud_vector_hints": [
            "ITIN", "synthetic identity", "mule", "tax return",
            "EIN", "immigration consultant", "fake visa",
        ],
    },
}

BBB_BASE = "https://www.bbb.org/scamtracker/lookupscam"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ── RSC flight data parser ───────────────────────────────────────────────────

def build_query_string(params):
    """Build the encoded q= parameter for BBB search URL."""
    parts = [f"{k}={v}" for k, v in params.items()]
    q_inner = "&".join(parts)
    return quote(q_inner, safe="")


def extract_scam_results(html):
    """Extract scam records from Next.js RSC flight data in HTML.

    BBB embeds Elasticsearch results inside self.__next_f.push() blocks
    as escaped JSON under a "scamResult" key. We find that block,
    unescape it, parse the JSON, and return the _source objects.
    """
    # Find the push block containing scamResult
    push_pattern = re.compile(
        r'self\.__next_f\.push\(\[\d+,"(.*?scamResult.*?)"\]\)', re.DOTALL
    )
    match = push_pattern.search(html)
    if not match:
        return []

    raw = match.group(1)

    # Unescape: the content is a JS string with escaped quotes/newlines
    # Order matters: unescape \\" first, then \"
    unescaped = raw.replace('\\"', '"')

    # Extract the scamResult JSON object using brace balancing
    sr_idx = unescaped.find('"scamResult":')
    if sr_idx == -1:
        return []

    # Find the opening brace of the scamResult value
    obj_start = unescaped.index('{', sr_idx)
    brace_count = 0
    obj_end = obj_start
    for i in range(obj_start, len(unescaped)):
        if unescaped[i] == '{':
            brace_count += 1
        elif unescaped[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                obj_end = i + 1
                break

    try:
        scam_result = json.loads(unescaped[obj_start:obj_end])
    except json.JSONDecodeError:
        return []

    # Extract _source from each hit
    results = []
    for hit in scam_result.get("hits", []):
        source = hit.get("_source", {})
        if source.get("scam_id") and source.get("description"):
            results.append(source)

    return results


def fetch_bbb_page(query_params, offset=0):
    """Fetch a BBB Scam Tracker search page and extract scam data."""
    query_params_with_offset = {**query_params, "from": str(offset)}
    q_encoded = build_query_string(query_params_with_offset)
    url = f"{BBB_BASE}?q={q_encoded}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return extract_scam_results(resp.text)
    except Exception as e:
        query_desc = "&".join(f"{k}={v}" for k, v in query_params.items())
        print(f"    BBB fetch error ({query_desc}): {e}")
        return []


# ── Fraud vector detection ───────────────────────────────────────────────────

def detect_fraud_vector(text, hints):
    """Tag likely fraud vector from description."""
    text_lower = text.lower()
    for hint in hints:
        if hint.lower() in text_lower:
            return hint
    return "unknown"


# ── Scraping logic ───────────────────────────────────────────────────────────

def scrape_archetype(archetype_name, config, output_dir="datasets", pages_per_query=3):
    """Scrape BBB Scam Tracker for one archetype."""
    print(f"\n{'='*60}")
    print(f"BBB scraping: {archetype_name.upper()}")
    print(f"{'='*60}")

    results = []
    seen_ids = set()

    for query_params in config["queries"]:
        query_desc = "&".join(f"{k}={v}" for k, v in query_params.items())
        print(f"  Searching: {query_desc}")

        for page in range(pages_per_query):
            offset = page * 10
            scams = fetch_bbb_page(query_params, offset=offset)

            if not scams:
                break

            for scam in scams:
                scam_id = str(scam.get("scam_id", ""))
                description = scam.get("description", "")

                if not description or scam_id in seen_ids:
                    continue
                if len(description) < 50:
                    continue

                seen_ids.add(scam_id)

                record = {
                    "id": f"bbb_{scam_id}",
                    "archetype": archetype_name,
                    "source": "bbb_scamtracker",
                    "scam_type": scam.get("scam_type", ""),
                    "scam_name": scam.get("scam_name", ""),
                    "narrative_text": description[:2000],
                    "dollar_value": scam.get("dollar_value", 0),
                    "target_state": scam.get("target_state", ""),
                    "target_country": scam.get("target_country", ""),
                    "scammer_business": scam.get("scammer_business_name", ""),
                    "scammer_url": scam.get("scammer_url", ""),
                    "date_reported": scam.get("createdOn", ""),
                    "detected_language_hints": ["en"],
                    "fraud_vector_hint": detect_fraud_vector(
                        description, config["fraud_vector_hints"]
                    ),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
                results.append(record)
                desc_safe = description[:55].encode("ascii", "replace").decode()
                print(f"    + [#{scam_id}] {desc_safe}...")

            time.sleep(2.0)  # courtesy delay between pages

    # Save
    out_dir = os.path.join(output_dir, archetype_name, "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "seed_narratives_bbb.jsonl")

    with open(out_path, "w", encoding="utf-8") as f:
        for record in results:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n  -> Saved {len(results)} BBB records to {out_path}")
    return results


def run_all(output_dir="datasets", archetypes_to_run=None):
    """Run BBB scraper for all (or specified) archetypes."""
    print("BBB Scam Tracker Scraper")
    print("No API key required -- parses server-rendered pages")
    print(f"Output directory: {output_dir}")

    targets = archetypes_to_run or list(ARCHETYPES.keys())
    print(f"Archetypes: {targets}\n")

    summary = {}
    for name in targets:
        config = ARCHETYPES[name]
        records = scrape_archetype(name, config, output_dir=output_dir)
        summary[name] = len(records)

    print(f"\n{'='*60}")
    print("BBB SCRAPE COMPLETE -- Summary")
    print(f"{'='*60}")
    for name, count in summary.items():
        status = "OK" if count >= 10 else f"LOW ({count} < 10 target)"
        print(f"  {status} -- {name}: {count} records")
    print(f"\nAll files: {output_dir}/{{archetype}}/raw/seed_narratives_bbb.jsonl")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BBB Scam Tracker scraper -- no API keys needed"
    )
    parser.add_argument("--output_dir", default="datasets",
                        help="Root output directory (default: datasets/)")
    parser.add_argument("--archetypes", nargs="+",
                        choices=["remittance", "gig_worker", "unbanked", "itin"],
                        help="Which archetypes to scrape (default: all 4)")
    args = parser.parse_args()

    run_all(output_dir=args.output_dir, archetypes_to_run=args.archetypes)