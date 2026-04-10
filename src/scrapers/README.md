# Scrapers — Seed Narrative Collection

Collects real-world fraud/scam narratives as seed data for synthetic dataset generation.
**No API keys required** — all sources are public.

## Sources

| Source | Coverage | Auth Required |
|--------|----------|---------------|
| Pullpush.io (Reddit archive) | English, Spanish, Hinglish, Tamil, Haitian Creole, Yoruba | None |
| BBB Scam Tracker | English scam reports with dollar-loss data | None |
| CFPB Complaint DB | English consumer complaints | None |

## Quick Start

### 1. Install dependencies
```bash
pip install requests beautifulsoup4
```

### 2. Run all scrapers
```bash
# All 4 archetypes
python run_all_scrapers.py

# Specific archetypes only
python run_all_scrapers.py --archetypes remittance gig_worker
```

### 3. Run individual scrapers
```bash
python web_scraper.py                          # Reddit archive + BBB
python cfpb_scraper.py                         # CFPB complaints only
python web_scraper.py --archetypes itin unbanked
```

## Output Structure

```
datasets/
├── remittance/raw/
│   ├── seed_narratives_web.jsonl    <- Reddit archive + BBB
│   ├── seed_narratives_cfpb.jsonl   <- CFPB complaints
│   ├── seed_narratives.jsonl        <- MERGED (use this for next steps)
│   └── scrape_summary.json          <- Stats + readiness flags
├── gig_worker/raw/
│   └── ...
├── unbanked/raw/
│   └── ...
└── itin/raw/
    └── ...
```

## Output Schema (seed_narratives.jsonl)

Each line is a JSON record:
```json
{
  "id": "reddit_abc123",
  "archetype": "remittance",
  "source": "reddit_archive",
  "subreddit": "scams",
  "narrative_text": "I was trying to send money to my family in Mexico...",
  "detected_language_hints": ["es", "en"],
  "fraud_vector_hint": "estafa",
  "scraped_at": "2026-04-11T10:00:00"
}
```

## Next Steps After Scraping

1. Upload `seed_narratives.jsonl` to **Adaptive Data** for reshaping & expansion
2. Run `src/generators/narrative_generator.py` to generate multilingual variants
3. Run `src/generators/tabddpm_generator.py` to generate synthetic transactions

## Target Counts

| Archetype | Minimum | Target |
|-----------|---------|--------|
| remittance | 50 | 75-100 |
| gig_worker | 50 | 75-100 |
| unbanked | 40 | 60-80 |
| itin | 40 | 60-80 |

If counts are low, check `scrape_summary.json` -> `ready_for_adaptive_data` flag.
Adaptive Data can expand even 20-30 seed narratives into a rich corpus.