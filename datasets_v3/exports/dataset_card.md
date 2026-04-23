# Persona-Conditioned Fraud Detection Dataset (v3, Citation-Grounded)

## What's new in v3 vs v2

v3 upgrades the **input** to v2's generation pipeline. Every persona field
is grounded in a real-world source (FinCEN advisories, FDIC microdata, Urban
Institute reports, Menjívar et al. TPS survey, Del Real Venezuelan migration
interviews, Remitly 10-K, Wise / Inter-American-Dialogue industry reports,
Treasury OIG fraud alerts, IRS SOI filer statistics). Every fraud vector is
mapped to a FinCEN typology code (FTA Identity 2024 or SAR Advisory Key Term).

**Three new universal columns on every transaction**:

| Field | Type | Description |
|---|---|---|
| `persona_source_ids` | list[str] | Citation IDs for real-world sources that grounded this record's persona |
| `fraud_vector_typology_ref` | string (nullable) | FinCEN typology reference for the row's fraud_vector; null on legit rows |
| `behavioral_evidence_grade` | categorical A/B/C/D | Quality grade of the evidence behind the persona (A=ethnographic, B=regulatory, C=industry research, D=design) |

Generation machinery is otherwise identical to v2 (Tab-DDPM-style
persona-conditioned sampling with joint platform→hour→amount for gig workers,
five v2 tightening rules, Adaption Labs narrative fill). Only the conditioning
input changes.

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total transactions | 20,000 (5,000 per archetype) |
| Total personas | 46 (12/12/10/12 for remittance/gig/unbanked/itin) |
| Sources in registry | 13 |
| FinCEN typology codes | 25 (14 FTA Identity 2024 + 11 SAR Advisory Key Terms) |
| Overall grade distribution | A: 6.2%, B: 50.0%, C: 22.9%, D: 20.8% |
| fraud_vector_typology_ref populated | 9.8% (= fraud rate; null on legit rows) |

## Per-archetype coverage

| Archetype | Rows | Narrative fill rate | Source of transactions |
|---|---:|---:|---|
| remittance | 5,000 | 99.8% | narrative_filled |
| gig_worker | 5,000 | 99.8% | narrative_filled |
| unbanked | 5,000 | 99.7% | narrative_filled |
| itin | 5,000 | 99.7% | narrative_filled |

## Schema (per transaction row)

| Field | Type | Description |
|---|---|---|
| data_uuid | string | Unique identifier |
| persona_id | string | Source persona (e.g., rem_004, gig_001) — join to `personas` |
| archetype | string | remittance, gig_worker, unbanked, itin |
| dataset_version | string | "v3" |
| transaction_amount_usd | float | USD amount |
| fee_amount_usd | float | USD fee |
| sender_age | int | Jitter around persona's age |
| hour_of_day | int | Persona-window constrained hour |
| day_of_week | int | 0=Mon .. 6=Sun |
| day_of_week_name | string | Mon/Tue/... |
| days_since_last_txn | int | Cadence-derived |
| account_age_days | int | Tenure-derived |
| txn_count_30d | int | Cadence-derived monthly count |
| instrument | string | Payment method / platform |
| language | string | From persona's language_mix |
| narrative_text | string | Adaption-generated first-person narrative |
| detected_language_hints | list[string] | Languages detected |
| fraud_vector | string | Fraud type or instrument label |
| fraud_vector_hint | string | Same as fraud_vector for legacy compatibility |
| is_fraud | int | 0=legit, 1=fraud |
| device_type | string | Persona's device |
| device_stability | float | Device churn proxy |
| record_timestamp | string | ISO timestamp |
| source | string | "tabddpm_v3_persona_grounded" |
| id | string | Legacy id field |
| **persona_source_ids** | list[string] | **v3 new**: citation IDs |
| **fraud_vector_typology_ref** | string (nullable) | **v3 new**: FinCEN typology code |
| **behavioral_evidence_grade** | string A/B/C/D | **v3 new**: evidence-quality grade |

## Generation Pipeline

```
persona_profiles.json  (46 grounded personas, per-field source attribution)
    └── TabDDPM v3 generator
        (PLATFORM_DB for gig_worker; archetype defaults + persona fields for others;
         per-persona fraud-vector weighting from family_crisis_history;
         joint platform→hour→amount sampling; five v2 tightening rules;
         FinCEN typology resolution on fraud rows)
        └── transactions.parquet (5k per archetype)
            └── Adaption Labs narrative fill (persona-anchored prompts)
                └── transactions_adapted.parquet (with narrative_text)
```

## Files

| File | Description |
|------|-------------|
| `transactions_v3_20k.parquet` | Combined 20,000-row dataset across 4 archetypes |
| `transactions_v3_20k.csv` | CSV version |
| `personas_all.json` | 46 persona profiles with per-field grounding and evidence grades |
| `sources.json` | Citation registry (13 entries: 7 PDFs, 1 data bundle, 5 links) |
| `typology_registry.json` | 25 FinCEN typology codes (14 FTA + 11 SAR advisories) |

## Credits

Adaption Labs — Expand-World and narrative fill (for v3, narrative fill only).
Source contributors: FinCEN, FDIC, US Census Bureau, Urban Institute,
Inter-American Dialogue, Remitly, Wise, Oxfam America, Treasury OIG, IRS SOI,
Federal Reserve (FedPayments Improvement), Cecilia Menjívar, Deisy Del Real,
Steven Vallas, Juliet Schor.
