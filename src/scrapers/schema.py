"""
schema.py
=========
Canonical schema for seed narrative records across all 4 archetypes.
Derived by reading every JSONL from web (Pullpush), CFPB, and BBB scrapers
and identifying field patterns across 1,040 records.

Design:
    - UNIVERSAL fields appear in every record regardless of source.
    - SOURCE-EXTENSION fields are populated only by a specific scraper.
    - All records conform to SeedNarrative (universal + extensions as Optional).

Usage:
    from schema import SeedNarrative, validate_record, normalize_record
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone
import json
import uuid


# ── Enums / Constants ────────────────────────────────────────────────────────

ARCHETYPES = ("remittance", "gig_worker", "unbanked", "itin")

SOURCES = ("reddit_archive", "cfpb", "bbb_scamtracker")

LANGUAGES = ("en", "es", "hi", "ta", "ta-en", "ht", "yo", "vi")

FRAUD_VECTORS = (
    "account takeover", "ATO", "advance fee", "emergency", "EIN",
    "estafa", "exchange rate", "fake family", "fake loan", "fake support",
    "fake visa", "fraude", "hacked", "hawala", "identity theft",
    "immigration consultant", "interception", "ITIN", "kiosk", "load fee",
    "mule", "OTP", "PayPal", "predatory", "prepaid", "robo identidad",
    "SIM swap", "social engineering", "stolen", "synthetic identity",
    "tax return", "wire transfer", "unknown",
)


# ── Universal Schema ─────────────────────────────────────────────────────────
# These 9 fields are populated in EVERY record from EVERY source.

@dataclass
class SeedNarrative:
    # ── Universal (always present) ────────────────────────────────────────
    data_uuid: str                       # UUID v4 — globally unique record identifier
    id: str                              # Source-scoped ID, prefixed: reddit_abc, cfpb_123, bbb_456
    archetype: str                       # One of ARCHETYPES
    source: str                          # One of SOURCES
    narrative_text: str                  # The fraud/scam narrative (max 2000 chars)
    detected_language_hints: list        # e.g. ["en"], ["es", "en"], ["ta-en"]
    fraud_vector_hint: str               # Best-guess fraud vector tag
    record_timestamp: str                # ISO 8601 timestamp of when record was collected

    # ── Reddit archive extensions (source=reddit_archive) ────────────────
    subreddit: Optional[str] = None      # Subreddit name, e.g. "scams", "WesternUnion"
    title: Optional[str] = None          # Reddit post title
    url: Optional[str] = None            # Permalink to Reddit post
    upvotes: Optional[int] = None        # Post score at time of scrape
    created_utc: Optional[str] = None    # Original post timestamp (ISO 8601)
    search_term_used: Optional[str] = None  # Query that found this post

    # ── CFPB extensions (source=cfpb) ────────────────────────────────────
    product: Optional[str] = None        # CFPB product category
    sub_product: Optional[str] = None    # CFPB sub-product
    issue: Optional[str] = None          # CFPB issue category
    sub_issue: Optional[str] = None      # CFPB sub-issue
    company: Optional[str] = None        # Company complained about
    state: Optional[str] = None          # US state of complainant
    date_received: Optional[str] = None  # Date CFPB received complaint
    submitted_via: Optional[str] = None  # Submission channel (Web, Phone, etc.)
    matched_keyword: Optional[str] = None  # Which archetype keyword matched

    # ── BBB Scam Tracker extensions (source=bbb_scamtracker) ─────────────
    scam_type: Optional[str] = None      # BBB scam category (e.g. "Phishing", "Identity Theft")
    scam_name: Optional[str] = None      # Scam title/label
    dollar_value: Optional[float] = None # Reported dollar loss
    target_state: Optional[str] = None   # Victim's US state
    target_country: Optional[str] = None # Victim's country
    scammer_business: Optional[str] = None  # Scammer business name
    scammer_url: Optional[str] = None    # Scammer website
    date_reported: Optional[str] = None  # Date scam was reported to BBB


# ── Validation ───────────────────────────────────────────────────────────────

REQUIRED_FIELDS = ("data_uuid", "id", "archetype", "source", "narrative_text",
                    "detected_language_hints", "fraud_vector_hint", "record_timestamp")


def validate_record(record: dict) -> list:
    """Validate a record dict against the schema. Returns list of errors (empty = valid)."""
    errors = []

    # Required fields
    for f in REQUIRED_FIELDS:
        if f not in record or record[f] is None:
            errors.append(f"missing required field: {f}")
        elif f == "narrative_text" and len(record[f]) < 50:
            errors.append(f"narrative_text too short ({len(record[f])} chars, min 50)")

    # Archetype check
    if record.get("archetype") and record["archetype"] not in ARCHETYPES:
        errors.append(f"invalid archetype: {record['archetype']}")

    # Source check
    if record.get("source") and record["source"] not in SOURCES:
        errors.append(f"invalid source: {record['source']}")

    # Language hints check
    hints = record.get("detected_language_hints", [])
    if not isinstance(hints, list) or len(hints) == 0:
        errors.append("detected_language_hints must be a non-empty list")

    return errors


# ── Normalization ────────────────────────────────────────────────────────────

def normalize_record(record: dict) -> dict:
    """Normalize a raw scraped record to conform to SeedNarrative schema.

    - Renames scraped_at -> record_timestamp (backward compat)
    - Generates data_uuid if missing
    - Strips unknown fields
    - Coerces types
    - Fills missing optional fields with None
    - Truncates narrative_text to 2000 chars
    """
    # Backward compat: rename scraped_at -> record_timestamp
    if "scraped_at" in record and "record_timestamp" not in record:
        record["record_timestamp"] = record.pop("scraped_at")

    # Generate UUID if missing
    if "data_uuid" not in record or not record["data_uuid"]:
        record["data_uuid"] = str(uuid.uuid4())

    fields = {f.name for f in SeedNarrative.__dataclass_fields__.values()}
    normalized = {}

    for f in fields:
        val = record.get(f)

        # Type coercion
        if f == "detected_language_hints" and isinstance(val, str):
            val = [val]
        if f == "upvotes" and val is not None:
            try:
                val = int(val)
            except (ValueError, TypeError):
                val = None
        if f == "dollar_value" and val is not None:
            try:
                val = float(val)
            except (ValueError, TypeError):
                val = None
        if f == "narrative_text" and isinstance(val, str):
            val = val[:2000]

        normalized[f] = val

    return normalized


def to_dataclass(record: dict) -> SeedNarrative:
    """Convert a dict to a SeedNarrative dataclass instance."""
    normalized = normalize_record(record)
    return SeedNarrative(**normalized)


def to_dict(narrative: SeedNarrative) -> dict:
    """Convert a SeedNarrative to a dict, dropping None optional fields."""
    d = asdict(narrative)
    return {k: v for k, v in d.items() if v is not None}


# ── JSONL I/O helpers ────────────────────────────────────────────────────────

def read_jsonl(path: str) -> list:
    """Read a JSONL file and return list of validated SeedNarrative dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            errors = validate_record(record)
            if errors:
                print(f"  Line {i}: {errors}")
            records.append(normalize_record(record))
    return records


def write_jsonl(records: list, path: str):
    """Write list of record dicts to JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            clean = {k: v for k, v in record.items() if v is not None}
            f.write(json.dumps(clean, ensure_ascii=False) + "\n")


# ── Schema summary (for inspection) ─────────────────────────────────────────

SCHEMA_SUMMARY = {
    "universal": {
        "data_uuid":                "str  — UUID v4, globally unique record identifier",
        "id":                       "str  — source-scoped ID, prefixed (reddit_, cfpb_, bbb_)",
        "archetype":                "str  — remittance | gig_worker | unbanked | itin",
        "source":                   "str  — reddit_archive | cfpb | bbb_scamtracker",
        "narrative_text":           "str  — fraud/scam narrative, 50-2000 chars",
        "detected_language_hints":  "list — ISO 639 codes: en, es, hi, ta, ta-en, ht, yo, vi",
        "fraud_vector_hint":        "str  — best-guess fraud vector tag",
        "record_timestamp":         "str  — ISO 8601 timestamp of when record was collected",
    },
    "reddit_archive_extensions": {
        "subreddit":       "str  — subreddit name",
        "title":           "str  — post title",
        "url":             "str  — permalink",
        "upvotes":         "int  — post score",
        "created_utc":     "str  — original post timestamp",
        "search_term_used":"str  — query that found this post",
    },
    "cfpb_extensions": {
        "product":         "str  — CFPB product category",
        "sub_product":     "str  — CFPB sub-product",
        "issue":           "str  — CFPB issue category",
        "sub_issue":       "str  — CFPB sub-issue (often null)",
        "company":         "str  — company complained about",
        "state":           "str  — US state (2-letter)",
        "date_received":   "str  — ISO 8601",
        "submitted_via":   "str  — Web, Phone, etc.",
        "matched_keyword": "str  — archetype keyword that matched",
    },
    "bbb_extensions": {
        "scam_type":        "str   — BBB category (Identity Theft, Phishing, etc.)",
        "scam_name":        "str   — scam title/label",
        "dollar_value":     "float — reported dollar loss (40% populated)",
        "target_state":     "str   — victim US state",
        "target_country":   "str   — victim country",
        "scammer_business": "str   — scammer business name (85% populated)",
        "scammer_url":      "str   — scammer website (43% populated)",
        "date_reported":    "str   — date reported to BBB",
    },
}


if __name__ == "__main__":
    print("SEED NARRATIVE SCHEMA")
    print("=" * 60)
    for section, fields in SCHEMA_SUMMARY.items():
        print(f"\n  {section.upper()}")
        print(f"  {'-'*56}")
        for name, desc in fields.items():
            print(f"    {name:<28} {desc}")

    print(f"\n\nTotal field count: {len(SeedNarrative.__dataclass_fields__)}")
    print(f"  Universal:  {len(SCHEMA_SUMMARY['universal'])} (incl. data_uuid + record_timestamp)")
    print(f"  Reddit ext: {len(SCHEMA_SUMMARY['reddit_archive_extensions'])}")
    print(f"  CFPB ext:   {len(SCHEMA_SUMMARY['cfpb_extensions'])}")
    print(f"  BBB ext:    {len(SCHEMA_SUMMARY['bbb_extensions'])}")