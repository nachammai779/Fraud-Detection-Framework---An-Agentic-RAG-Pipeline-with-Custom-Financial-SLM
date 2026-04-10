"""
cfpb_scraper.py
===============
Scrapes the Consumer Financial Protection Bureau (CFPB) public complaint
database for seed narratives across all 4 archetypes.

No API key required — CFPB complaint database is fully public.
API docs: https://cfpb.github.io/api/ccdb/

Usage:
    python cfpb_scraper.py
    python cfpb_scraper.py --archetypes remittance gig_worker
"""

import requests
import json
import time
import argparse
import os
from datetime import datetime

CFPB_BASE = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"

# ── Archetype → CFPB product/issue filters ───────────────────────────────────

ARCHETYPE_FILTERS = {

    "remittance": {
        "products": [
            "Money transfer, virtual currency, or money service",
            "Money transfers",
        ],
        "issues": [
            "Money was not available when promised",
            "Fraud or scam",
            "Other transaction problem",
            "Wrong amount charged or received",
            "Unexpected or other fees",
        ],
        "keywords": [
            "remittance", "wire transfer", "Western Union", "MoneyGram",
            "Remitly", "Xoom", "exchange rate", "family emergency",
            "international transfer", "send money"
        ]
    },

    "gig_worker": {
        "products": [
            "Money transfer, virtual currency, or money service",
            "Checking or savings account",
            "Prepaid card",
        ],
        "issues": [
            "Fraud or scam",
            "Unauthorized transactions or other transaction problem",
            "Problem adding money",
            "Problem with a lender or other company charging your account",
        ],
        "keywords": [
            "CashApp", "Venmo", "Zelle", "PayPal", "account hacked",
            "unauthorized transfer", "SIM swap", "account takeover",
            "gig", "driver", "Uber", "DoorDash", "instant pay"
        ]
    },

    "unbanked": {
        "products": [
            "Prepaid card",
            "Payday loan, title loan, or personal loan",
            "Payday loan",
            "Money transfer, virtual currency, or money service",
        ],
        "issues": [
            "Fraud or scam",
            "Unexpected or other fees",
            "Problem getting a line of credit",
            "Charged fees or interest you didn't expect",
            "Struggling to pay your loan",
        ],
        "keywords": [
            "prepaid card", "payday loan", "cash advance", "load fee",
            "kiosk", "no bank account", "unbanked", "advance fee",
            "predatory", "high fee", "bill pay"
        ]
    },

    "itin": {
        "products": [
            "Credit reporting, credit repair services, or other personal consumer reports",
            "Debt collection",
            "Checking or savings account",
            "Mortgage",
        ],
        "issues": [
            "Incorrect information on your report",
            "Identity theft protection or other monitoring services",
            "Fraud or scam",
            "Problem with fraud alerts or security freezes",
        ],
        "keywords": [
            "ITIN", "identity theft", "tax return", "synthetic identity",
            "immigrant", "EIN", "social security", "credit fraud",
            "immigration", "small business fraud", "mule account"
        ]
    }
}


def fetch_cfpb_complaints(product, issue, size=50, page=0):
    """Fetch complaints from CFPB API for a product/issue combination."""
    params = {
        "product": product,
        "issue": issue,
        "has_narrative": "true",
        "size": size,
        "frm": page * size,
    }
    try:
        resp = requests.get(CFPB_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("hits", {}).get("hits", [])
    except Exception as e:
        print(f"    CFPB API error: {e}")
        return []


def keyword_match(narrative, keywords):
    """Check if any keyword appears in the narrative."""
    if not narrative:
        return False, None
    narrative_lower = narrative.lower()
    for kw in keywords:
        if kw.lower() in narrative_lower:
            return True, kw
    return False, None


def scrape_archetype_cfpb(archetype_name, config, output_dir="datasets", max_per_combo=30):
    """Scrape CFPB for one archetype."""
    print(f"\n{'='*60}")
    print(f"CFPB scraping: {archetype_name.upper()}")
    print(f"{'='*60}")

    results = []
    seen_ids = set()

    for product in config["products"]:
        for issue in config["issues"]:
            print(f"  Fetching: product='{product[:40]}...' issue='{issue[:40]}'")
            hits = fetch_cfpb_complaints(product, issue, size=max_per_combo)

            for hit in hits:
                src = hit.get("_source", {})
                complaint_id = src.get("complaint_id", "")
                narrative = src.get("complaint_what_happened", "") or src.get("consumer_complaint_narrative", "")

                if not narrative or complaint_id in seen_ids:
                    continue

                matched, matched_kw = keyword_match(narrative, config["keywords"])
                if not matched:
                    continue  # only keep keyword-relevant complaints

                seen_ids.add(complaint_id)

                record = {
                    "id": f"cfpb_{complaint_id}",
                    "archetype": archetype_name,
                    "source": "cfpb",
                    "product": src.get("product", ""),
                    "sub_product": src.get("sub_product", ""),
                    "issue": src.get("issue", ""),
                    "sub_issue": src.get("sub_issue", ""),
                    "narrative_text": narrative[:2000],
                    "company": src.get("company", ""),
                    "state": src.get("state", ""),
                    "submitted_via": src.get("submitted_via", ""),
                    "date_received": src.get("date_received", ""),
                    "matched_keyword": matched_kw,
                    "detected_language_hints": ["en"],  # CFPB is English-dominant
                    "fraud_vector_hint": matched_kw or "unknown",
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                results.append(record)
                narr_safe = narrative[:60].encode("ascii", "replace").decode()
                print(f"    + [{complaint_id}] matched '{matched_kw}' -- {narr_safe}...")

            time.sleep(0.5)  # rate limit courtesy

    # Save
    out_dir = os.path.join(output_dir, archetype_name, "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "seed_narratives_cfpb.jsonl")

    with open(out_path, "w", encoding="utf-8") as f:
        for record in results:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n  -> Saved {len(results)} CFPB records to {out_path}")
    return results


def run_all_cfpb(output_dir="datasets", archetypes_to_run=None):
    """Run CFPB scraper for all archetypes."""
    print("CFPB Public Complaint Database Scraper")
    print("No API key required — public data")
    print(f"Output: {output_dir}/{{archetype}}/raw/seed_narratives_cfpb.jsonl\n")

    targets = archetypes_to_run or list(ARCHETYPE_FILTERS.keys())
    summary = {}

    for name in targets:
        config = ARCHETYPE_FILTERS[name]
        records = scrape_archetype_cfpb(name, config, output_dir=output_dir)
        summary[name] = len(records)

    print(f"\n{'='*60}")
    print("CFPB SCRAPE COMPLETE — Summary")
    print(f"{'='*60}")
    for name, count in summary.items():
        status = "OK" if count >= 20 else "LOW (below 20 target -- CFPB is supplementary)"
        print(f"  {status} {name}: {count} records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CFPB seed narrative scraper")
    parser.add_argument("--output_dir", default="datasets")
    parser.add_argument("--archetypes", nargs="+",
                        choices=["remittance", "gig_worker", "unbanked", "itin"])
    args = parser.parse_args()

    run_all_cfpb(output_dir=args.output_dir, archetypes_to_run=args.archetypes)
