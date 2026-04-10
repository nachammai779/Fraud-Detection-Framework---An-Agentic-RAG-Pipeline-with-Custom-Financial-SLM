"""
web_scraper.py
==============
Scrapes fraud/scam seed narratives from public sources — NO API keys required.

Sources:
    1. Pullpush.io  — free Reddit archive API (no auth, no rate-limit keys)
    2. BBB Scam Tracker — Better Business Bureau public scam reports

Usage:
    python web_scraper.py
    python web_scraper.py --archetypes remittance gig_worker
"""

import requests
import json
import time
import argparse
import os
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# ── Archetype search configuration ───────────────────────────────────────────

ARCHETYPES = {

    "remittance": {
        "subreddits": [
            "Remitly", "WesternUnion", "scams", "personalfinance",
            "immigration", "moneytransfer", "nigeria", "mexico",
            "haiti", "ghana", "philippines"
        ],
        "search_terms": [
            "remittance scam", "money transfer fraud", "Western Union scam",
            "Remitly problem", "MoneyGram fraud", "wire transfer scam",
            "fake exchange rate", "emergency transfer scam",
            "estafa remesa", "fraude envío dinero", "estafa Western Union",
            "fraude transferencia", "tasa cambio falsa",
            "Haiti scam money", "Haitian fraud transfer",
            "Nigeria wire fraud", "Yoruba scam transfer", "Ghana remittance fraud",
        ],
        "fraud_vector_hints": [
            "interception", "emergency", "exchange rate", "bonus", "fake family",
            "estafa", "fraude", "engano",
        ],
        "bbb_keywords": [
            "wire transfer", "money transfer", "remittance", "Western Union",
            "MoneyGram", "exchange rate",
        ],
    },

    "gig_worker": {
        "subreddits": [
            "UberDrivers", "doordash_drivers", "InstacartShoppers",
            "CashApp", "venmo", "scams", "Fiverr", "WorkOnline",
            "AbcDesis", "india", "tamil",
        ],
        "search_terms": [
            "account hacked driver", "stolen earnings gig",
            "CashApp scam driver", "Venmo account takeover",
            "SMS scam uber", "fake support call driver",
            "SIM swap gig worker", "instant pay stolen",
            "DoorDash account stolen", "platform support scam",
            "account hack ho gaya", "paise chori", "OTP scam driver",
            "UPI fraud driver", "Paytm scam",
            "Tamil driver scam", "fraud uber driver india",
        ],
        "fraud_vector_hints": [
            "account takeover", "ATO", "SIM swap", "OTP", "social engineering",
            "fake support", "hacked", "stolen", "paise", "hack ho",
        ],
        "bbb_keywords": [
            "gig worker", "Uber", "DoorDash", "CashApp", "Venmo",
            "account takeover", "driver scam",
        ],
    },

    "unbanked": {
        "subreddits": [
            "povertyfinance", "personalfinance", "scams",
            "Loans", "payday", "prepaidcards", "Vietnam",
            "Somalia", "immigrants", "Frugal",
        ],
        "search_terms": [
            "prepaid card scam", "load fee fraud", "fake loan app",
            "payday loan fraud", "cash advance scam", "kiosk fraud",
            "utility payment scam", "predatory loan", "advance fee loan",
            "no bank account scam", "unbanked fraud",
            "estafa tarjeta prepagada", "fraude prestamo", "estafa sin banco",
            "fraude kiosco", "prestamo falso",
            "Vietnam money scam", "nail salon fraud",
            "Somali refugee scam", "hawala fraud",
        ],
        "fraud_vector_hints": [
            "load fee", "advance fee", "predatory", "fake loan", "kiosk",
            "prepaid", "estafa", "fraude prestamo", "hawala",
        ],
        "bbb_keywords": [
            "prepaid card", "payday loan", "cash advance", "loan scam",
            "advance fee", "predatory lending",
        ],
    },

    "itin": {
        "subreddits": [
            "immigration", "ITIN", "smallbusiness", "tax",
            "uscis", "india", "China", "korea", "legaladvice",
            "AbcDesis", "ChineseInAmerica",
        ],
        "search_terms": [
            "ITIN fraud", "ITIN scam", "tax identity theft immigrant",
            "synthetic identity fraud", "mule account immigrant",
            "fake immigration consultant", "tax return stolen ITIN",
            "identity theft small business", "EIN fraud immigrant",
            "fraude ITIN", "robo identidad ITIN", "consultor inmigracion falso",
            "fraude declaracion impuestos",
            "ITIN fraud India", "H1B identity theft",
            "immigration consultant fraud India",
            "fake visa consultant", "OCI fraud",
            "Chinese restaurant tax fraud",
            "Korean small business identity theft",
        ],
        "fraud_vector_hints": [
            "ITIN", "synthetic identity", "mule", "tax return", "EIN",
            "immigration consultant", "fake visa", "robo identidad",
        ],
        "bbb_keywords": [
            "ITIN", "identity theft", "tax fraud", "immigration consultant",
            "synthetic identity", "EIN fraud",
        ],
    },
}

# ── Language & fraud vector detection ────────────────────────────────────────

def detect_language_hint(text):
    """Simple heuristic language detection based on character patterns."""
    hints = []
    text_lower = text.lower()
    spanish_words = ["estafa", "fraude", "dinero", "banco", "tarjeta", "prestamo", "envio"]
    if any(w in text_lower for w in spanish_words):
        hints.append("es")
    hindi_words = ["paise", "rupee", "nahi", "gaya", "karo", "bhai", "yaar", "otp"]
    if any(w in text_lower for w in hindi_words):
        hints.append("hi")
    creole_words = ["lajan", "voye", "haiti", "ayisyen"]
    if any(w in text_lower for w in creole_words):
        hints.append("ht")
    yoruba_words = ["owo", "nigeria", "yoruba", "naira"]
    if any(w in text_lower for w in yoruba_words):
        hints.append("yo")
    viet_words = ["vietnam", "tien", "lua dao"]
    if any(w in text_lower for w in viet_words):
        hints.append("vi")
    tamil_words = ["panam", "mosadi", "kashtam", "yemaathu",
                    "ooru", "vangal", "pannunga", "thollai"]
    if any(w in text_lower for w in tamil_words):
        hints.append("ta")
    tanglish_words = ["podunga", "pannunga", "onlinela", "panlam", "account la", "pay pannunga"]
    if any(w in text_lower for w in tanglish_words):
        hints.append("ta-en")
    return hints if hints else ["en"]


def detect_fraud_vector(text, hints):
    """Tag likely fraud vector from post content."""
    text_lower = text.lower()
    for hint in hints:
        if hint.lower() in text_lower:
            return hint
    return "unknown"


# ── Source 1: Pullpush.io (Reddit archive — no auth) ─────────────────────────

PULLPUSH_SEARCH = "https://api.pullpush.io/reddit/search/submission/"

def fetch_pullpush(subreddit, query, limit=10, max_retries=3):
    """Search Reddit posts via Pullpush.io archive API (no API key needed)."""
    params = {
        "subreddit": subreddit,
        "q": query,
        "size": limit,
        "sort": "score",
        "sort_type": "desc",
    }
    for attempt in range(max_retries):
        try:
            resp = requests.get(PULLPUSH_SEARCH, params=params, timeout=20)
            if resp.status_code == 429:
                wait = 3 * (attempt + 1)
                print(f"    Rate limited — waiting {wait}s before retry...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            print(f"    Pullpush error [{subreddit}] '{query}': {e}")
            return []
    return []


def scrape_pullpush(archetype_name, config, max_per_term=8):
    """Scrape Reddit archive via Pullpush for one archetype."""
    print(f"\n  [Pullpush] Scraping r/ posts for: {archetype_name}")
    results = []
    seen_ids = set()

    for subreddit in config["subreddits"]:
        for term in config["search_terms"]:
            posts = fetch_pullpush(subreddit, term, limit=max_per_term)

            for post in posts:
                post_id = post.get("id", "")
                selftext = post.get("selftext", "")

                if post_id in seen_ids:
                    continue
                if selftext in ("[removed]", "[deleted]", ""):
                    continue
                if len(selftext) < 100:
                    continue

                seen_ids.add(post_id)
                full_text = f"{post.get('title', '')}. {selftext}"
                lang_hints = detect_language_hint(full_text)
                fraud_vector = detect_fraud_vector(full_text, config["fraud_vector_hints"])

                record = {
                    "id": f"reddit_{post_id}",
                    "archetype": archetype_name,
                    "source": "reddit_archive",
                    "subreddit": post.get("subreddit", subreddit),
                    "search_term_used": term,
                    "title": post.get("title", ""),
                    "narrative_text": selftext[:2000],
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "upvotes": post.get("score", 0),
                    "created_utc": datetime.fromtimestamp(
                        int(float(post.get("created_utc", 0))), tz=timezone.utc
                    ).isoformat() if post.get("created_utc") else "",
                    "detected_language_hints": lang_hints,
                    "fraud_vector_hint": fraud_vector,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
                results.append(record)
                title_safe = post.get("title", "")[:55].encode("ascii", "replace").decode()
                print(f"    + [r/{subreddit}] {title_safe}...")

            time.sleep(2.0)  # courtesy delay — avoid 429 rate limits

    print(f"  [Pullpush] {archetype_name}: {len(results)} posts collected")
    return results


# ── Source 2: BBB Scam Tracker (public, no auth) ─────────────────────────────

BBB_SCAM_SEARCH = "https://www.bbb.org/scamtracker/lookupscam"
BBB_API_SEARCH = "https://www.bbb.org/api/scamtracker/search"

def fetch_bbb_scams(keyword, page=1, page_size=20):
    """Fetch scam reports from BBB Scam Tracker search API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.bbb.org/scamtracker",
    }
    params = {
        "SearchText": keyword,
        "Page": page,
        "PageSize": page_size,
    }
    try:
        resp = requests.get(BBB_API_SEARCH, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", data) if isinstance(data, dict) else data
    except Exception as e:
        print(f"    BBB API error for '{keyword}': {e}")
        return []


def scrape_bbb(archetype_name, config, max_per_keyword=15):
    """Scrape BBB Scam Tracker for one archetype."""
    print(f"\n  [BBB] Scraping scam reports for: {archetype_name}")
    results = []
    seen_ids = set()

    for keyword in config.get("bbb_keywords", []):
        scams = fetch_bbb_scams(keyword, page_size=max_per_keyword)

        if isinstance(scams, list):
            items = scams
        elif isinstance(scams, dict):
            items = scams.get("items", scams.get("results", []))
        else:
            items = []

        for item in items:
            scam_id = str(item.get("id", item.get("scamId", "")))
            description = item.get("description", item.get("scamText", ""))

            if not description or scam_id in seen_ids:
                continue
            if len(description) < 50:
                continue

            seen_ids.add(scam_id)

            record = {
                "id": f"bbb_{scam_id}",
                "archetype": archetype_name,
                "source": "bbb_scamtracker",
                "scam_type": item.get("scamType", item.get("type", "")),
                "narrative_text": description[:2000],
                "amount_lost": item.get("amountLost", item.get("dollarLoss", "")),
                "date_reported": item.get("dateReported", item.get("createdDate", "")),
                "detected_language_hints": ["en"],
                "fraud_vector_hint": detect_fraud_vector(
                    description, config["fraud_vector_hints"]
                ),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            results.append(record)
            print(f"    + [BBB] {description[:55]}...")

        time.sleep(1.0)

    print(f"  [BBB] {archetype_name}: {len(results)} reports collected")
    return results


# ── Orchestration ─────────────────────────────────────────────────────────────

def scrape_archetype(archetype_name, config, output_dir="datasets"):
    """Scrape all web sources for one archetype and save JSONL."""
    print(f"\n{'='*60}")
    print(f"Web scraping archetype: {archetype_name.upper()}")
    print(f"{'='*60}")

    all_records = []

    # Source 1: Reddit archive via Pullpush
    all_records.extend(scrape_pullpush(archetype_name, config))

    # Source 2: BBB Scam Tracker
    all_records.extend(scrape_bbb(archetype_name, config))

    # Save combined output
    out_dir = os.path.join(output_dir, archetype_name, "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "seed_narratives_web.jsonl")

    with open(out_path, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n  -> Saved {len(all_records)} records to {out_path}")
    return all_records


def run_all(output_dir="datasets", archetypes_to_run=None):
    """Run web scraper for all (or specified) archetypes."""
    print("Web Scraper — No API keys required")
    print(f"Sources: Pullpush.io (Reddit archive) + BBB Scam Tracker")
    print(f"Output directory: {output_dir}")

    targets = archetypes_to_run or list(ARCHETYPES.keys())
    print(f"Archetypes: {targets}\n")

    summary = {}
    for name in targets:
        config = ARCHETYPES[name]
        records = scrape_archetype(name, config, output_dir=output_dir)
        summary[name] = len(records)

    print(f"\n{'='*60}")
    print("WEB SCRAPE COMPLETE — Summary")
    print(f"{'='*60}")
    for name, count in summary.items():
        status = "OK" if count >= 50 else f"LOW ({count} < 50 target)"
        print(f"  {status} — {name}: {count} records")
    print(f"\nAll files: {output_dir}/{{archetype}}/raw/seed_narratives_web.jsonl")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Web scraper for fraud seed narratives — no API keys needed"
    )
    parser.add_argument("--output_dir", default="datasets",
                        help="Root output directory (default: datasets/)")
    parser.add_argument("--archetypes", nargs="+",
                        choices=["remittance", "gig_worker", "unbanked", "itin"],
                        help="Which archetypes to scrape (default: all 4)")
    args = parser.parse_args()

    run_all(output_dir=args.output_dir, archetypes_to_run=args.archetypes)