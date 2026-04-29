# Persona-Conditioned Fraud Detection Dataset (v4 + v4.1, Full Typology Coverage)

## Summary

A 20,300-row citation-grounded synthetic fraud-narrative dataset for four
underserved US financial-system archetypes (remittance, gig_worker, unbanked,
ITIN). Every persona field is grounded in a real-world source (FinCEN
advisories, FDIC microdata, Urban Institute, Menjívar et al., Del Real,
Remitly, Wise, IAD, Oxfam, Treasury OIG, IRS SOI, Vallas & Schor, FedPayments
Improvement). Every fraud row is mapped to one of 25 FinCEN typology codes
(14 FTA Identity 2024 + 11 SAR Advisory Key Terms). All 25 codes are
exercised in the dataset.

## What's new in v4 (vs v3) and v4.1 (vs v4)

**v4** — closed FinCEN typology coverage from 10/25 to 18/25 via:

1. 16 persona edits adding documented fraud events (SIM-swap, BEC, hawala/
   IVTS, hurricane scams, money-mule, synthetic-ID, unauthorized-ACH,
   lax-KYC, false-chargeback, COVID-imposter). 8 grade upgrades D→B.
2. Typology resolver prefers SAR Advisory codes over FTA codes when both
   match a fraud_vector — surfaces specific advisory codes (ATO, BEC,
   Cyber, Disaster) instead of generic FTA labels.
3. Combined 20k Adaption narrative fill — single job, 20 languages, native
   scripts, persona/transaction context per prompt.

**v4.1** — closed coverage from 18/25 to **25/25** via:

1. Strip prompt-tag leakage from 1,235 narratives (Adaption was echoing the
   upload metadata block into completions for ~6% of rows).
2. Re-stamp 4 shadowed FTA codes (T4, T6, T9, T11) on a half-cap subset so
   both FTA and SAR equivalents carry rows. No Adaption credits.
3. Add 3 truly-missing codes (T7 Abuse of Access, T8 Refusal to Cooperate,
   SAR_HUMAN_TRAFFICKING) via persona-event additions on `unb_001`,
   `gig_001`, `itin_010` + 300 synthetic transactions narrated by Adaption.
4. Refill 51/52 empty narratives with the original prompts.

## Three universal columns from v3, updated v4 values

| Field | Type | Description |
|---|---|---|
| `persona_source_ids` | list[str] | Citation IDs that grounded this record's persona |
| `fraud_vector_typology_ref` | string (nullable) | FinCEN typology code for the row's fraud_vector; null on legit rows |
| `behavioral_evidence_grade` | string A/B/C/D | A=ethnographic, B=regulatory, C=industry research, D=design |

## Dataset Statistics

| Metric | Value |
|---|---|
| Total transactions | 20,300 |
| Per-archetype rows | remittance 5,000, gig_worker 5,100, unbanked 5,100, itin 5,100 |
| Total personas | 46 (12/12/10/12 across remittance/gig_worker/unbanked/itin) |
| Sources in registry | 13 |
| FinCEN typology codes | 25 registered, **25 exercised** in generated output |
| Languages | 20 tagged (en, es, vi, wo, yo, hi, fr, ko, zh, ru, tw, am, ar, ta, ja, te, fil, mr, ceb, gu); 92.8% tag↔detect match |
| Fraud rows | 2,263 (~11.1%) |
| Overall persona grade | A 6.3% / B 58.3% / C 22.9% / D 12.5% |
| Empty narratives | 39 (~0.19%) |
| Prompt-tag leakage | 0 (post-strip) |

## Per-archetype coverage

| Archetype | Rows | Fraud rows | Narrative fill rate |
|---|---:|---:|---:|
| remittance | 5,000 | 508 | 100.0% |
| gig_worker | 5,100 | 570 | 99.7% |
| unbanked | 5,100 | 585 | 99.8% |
| itin | 5,100 | 600 | 99.7% |

## Schema (per transaction row)

| Field | Type | Description |
|---|---|---|
| data_uuid | string | Unique identifier |
| persona_id | string | Source persona (e.g., rem_004, gig_001) — joins to `personas` |
| archetype | string | remittance / gig_worker / unbanked / itin |
| dataset_version | string | "v4" (most rows) or "v4.1" (300 rows added in patch layer) |
| transaction_amount_usd | float | USD amount |
| fee_amount_usd | float | USD fee |
| sender_age | int | Jitter around persona's age |
| hour_of_day | int | Persona-window constrained hour |
| day_of_week | int | 0=Mon … 6=Sun |
| day_of_week_name | string | Mon/Tue/… |
| days_since_last_txn | int | Cadence-derived |
| account_age_days | int | Tenure-derived |
| txn_count_30d | int | Cadence-derived monthly count |
| instrument | string | Payment method / platform |
| language | string | From persona's language_mix |
| narrative_text | string | Adaption-generated first-person narrative |
| detected_language_hints | list[string] | Languages detected on the narrative |
| fraud_vector | string | Fraud type or instrument label |
| fraud_vector_hint | string | Same as fraud_vector for legacy compatibility |
| is_fraud | int | 0=legit, 1=fraud |
| device_type | string | Persona's device |
| device_stability | float | Device churn proxy |
| record_timestamp | string | ISO timestamp |
| source | string | "tabddpm_v4_persona_grounded" |
| id | string | Legacy id field |
| **persona_source_ids** | list[string] | **v3/v4 column**: citation IDs |
| **fraud_vector_typology_ref** | string (nullable) | **v3/v4 column**: FinCEN typology code |
| **behavioral_evidence_grade** | string A/B/C/D | **v3/v4 column**: evidence-quality grade |

## Generation Pipeline

```
persona_profiles.json  (46 grounded personas, per-field source attribution)
    └── TabDDPM v4 generator
        (PLATFORM_DB for gig_worker; archetype defaults + persona fields for others;
         per-persona fraud-vector weighting from family_crisis_history;
         joint platform→hour→amount sampling; five v2 tightening rules;
         FinCEN typology resolution with SAR-preference)
        └── transactions.parquet (5k per archetype, 20k total)
            └── Combined 20k Adaption narrative fill (one job)
                └── Strip prompt-tag leakage (post-process)
                    └── transactions_adapted.parquet
                        └── v4.1 patch layer:
                            re-stamp shadowed codes (no credits)
                            add 3 missing-code persona events + 300 synth rows + Adaption fill
                            refill 51/52 empties
                            └── final 20,300-row dataset, 25/25 coverage
```

## Files

| File | Description |
|---|---|
| `transactions_v4_20k.parquet` | Combined 20,300-row dataset across 4 archetypes |
| `transactions_v4_20k.csv` | CSV mirror |
| `personas_all.json` | 46 persona profiles with per-field grounding and evidence grades |
| `sources.json` | 13-entry citation registry |
| `typology_registry.json` | 25 FinCEN typology codes (14 FTA + 11 SAR advisories) |
| `coverage.json` | Per-archetype narrative fill rates |
| `analysis_report.json` | Full propagation/coverage analysis |

## Companion artifact: CoT reasoning dataset

`datasets_v4/reasoning/cot_dataset.parquet` — 3,926 rows (1,963 fraud + 1,963
matched non-fraud) with chain-of-thought reasoning traces appended via
Adaption's `reasoning_traces` recipe. Adaption quality grade: E → A (+92%).
100% trace fill. Built for SFT/judge training; **not** part of the 20,300-row
bundle.

## Credits

- **Adaption Labs** — narrative fill (combined 20k v4 job + v4.1 patch + CoT)
- **FinCEN** — Financial Trend Analysis 2024 (Identity), SAR Advisory Key Terms
- **FDIC** — 2023 National Survey of Unbanked and Underbanked Households
- **Menjívar, Agadjanian & Oh** — "The Contradictions of Liminal Legality" (Soc Probl 2022)
- **Del Real** — "Seemingly inclusive liminal legality" (J Ethn Migr Stud 2022)
- **Vallas & Schor** — "What Do Platforms Do?" (Annu Rev Sociol 2020)
- **Remitly, Wise, Inter-American Dialogue, Oxfam America, IRS SOI, Treasury OIG, Federal Reserve FedPayments Improvement** — industry & regulatory sources
- **Tab-DDPM** — Gaussian multinomial diffusion for tabular data