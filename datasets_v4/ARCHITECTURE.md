# V4 Citation-Grounded Dataset Pipeline — Architecture Walkthrough

> v4.1 closed the remaining coverage gap to 25/25 typology codes via a small
> patch layer. See `v4_1/ARCHITECTURE.md` for that delta. This document
> describes v4 itself: the 20,000-row baseline through the combined Adaption
> narrative fill.

## What changed from v3

V3 shipped a citation-grounded dataset with 10 of 25 FinCEN typology codes
exercised. V4 closes most of that coverage gap through three targeted
generator-level changes, then replaces v3's narrative content with a fresh
20,000-row Adaption pass.

| Change | Effect |
|---|---|
| 16 persona edits (11 carried from a v3 draft + 5 new typology-focused) | Documented fraud events expanded across gig_worker, remittance, and unbanked personas; 8 persona grade upgrades (D→B) |
| Typology resolver rule: SAR advisories preferred over FTA codes when both match a fraud_vector | Surfaces 4 previously-shadowed SAR advisory codes (ATO, BEC, Cyber Events, Disaster-Related Fraud) in every fraud row |
| 9 new fraud-event regex patterns in the generator | New events like `hurricane_maria_fake_charity_scam_attempted_2018`, `ivts_ghanaian_merchant_network_recurring`, and `unauthorized_ach_greendot_prepaid_2024_reversed` map to the correct typology code at sampling time |
| Combined 20k Adaption narrative fill | Per-row narratives in 20 languages with persona/transaction context injected; replaces the planned v3 overlay |

**Typology coverage at v4 close: 18 of 25 codes exercised (+80% relative to v3).** v4.1 patches close to 25/25.

---

## Pipeline delta (v3 → v4)

```
V3:  sources.json + extracts -> synthesised persona_profiles
     -> TabDDPM v3 generator -> transactions.parquet
     -> Adaption narrative fill -> transactions_adapted.parquet

V4:  datasets_v3/ (frozen on HF) + 16 persona edits
     -> synthesised persona_profiles (v4)
     -> TabDDPM v4 generator (SAR-preference + expanded fraud patterns)
     -> transactions.parquet (new metadata columns, same shape)
     -> Combined 20k Adaption narrative fill -> transactions_adapted.parquet
     -> Post-process: strip prompt-tag leakage
```

The three universal v3 columns remain:

- `persona_source_ids` (list[str], persona-level)
- `behavioral_evidence_grade` (A/B/C/D, persona-level)
- `fraud_vector_typology_ref` (string|null, row-level, re-resolved per the SAR-preference rule)

All other row columns are unchanged.

---

## Stage 1 — Source registry (inherited, two extensions)

`datasets_v4/sources/` is a direct copy of `datasets_v3/sources/` with two
edits:

1. `fincen_sar_key_terms` and `fincen_2024_identity_fta` have `unbanked`
   added to their `archetypes` list. This makes the v4 edits to unb_003 and
   unb_009 (which reference these advisories) lint-clean. Rationale: both
   advisories contain content that applies to unbanked populations —
   SAR_ADVISORY_THIRD_PARTY_PAYMENT_PROCESSORS for prepaid-card ACH fraud,
   FTA_IDENTITY_2024_T5 Circumventing Standards for unlicensed MSB
   observations.
2. The FDIC HH2023 microdata bundle was **not** copied to v4 — v4's
   sources.json cross-references `datasets_v3/sources/pdfs/hh2023/` to avoid
   duplicating 650 MB of data. Citation paths in v4 point at v3's bundle.

All other source entries, 13 total, and the 25-code typology_registry are
bit-identical to v3.

---

## Stage 2 — V4 persona synthesis

All 46 v3 personas are carried forward. **16 persona-level edits** applied on
top:

### Group 1 — fraud-event additions, 11 edits (carried from a v3 draft)

| Persona | Event added | Typology exercised |
|---|---|---|
| gig_001 DeShawn | `sim_swap_account_takeover_attempted_2024` | SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD |
| gig_004 Ahmed | `bec_uber_driver_relations_impersonation_2024_detected` (backfill) | SAR_ADVISORY_BEC_FRAUD |
| gig_006 Hai (D→B) | `bec_salon_supplier_invoice_fraud_2024_detected` | SAR_ADVISORY_BEC_FRAUD |
| gig_009 Tyler | `synthetic_id_platform_account_duplicate_2024_detected` (backfill) | FTA_IDENTITY_2024_T13 |
| gig_011 Marcus | `account_takeover_credential_stuffing_2024_detected` (backfill) | SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD |
| gig_012 Alex | `phishing_taskrabbit_credential_compromise_2024_detected` | SAR_ADVISORY_CYBER_EVENTS |
| rem_002 Carlos | `hurricane_eta_relief_scam_attempted_2021` | SAR_ADVISORY_DISASTER_RELATED_FRAUD |
| rem_004 Oluwaseun | `family_requested_hawala_routing_2023_declined` | SAR_ADVISORY_IVTS |
| rem_009 Kwame | `ivts_ghanaian_merchant_network_recurring` | SAR_ADVISORY_IVTS |
| rem_011 Carmen | `hurricane_maria_fake_charity_scam_attempted_2018` | SAR_ADVISORY_DISASTER_RELATED_FRAUD |
| rem_012 Aleksandr (D→B) | `funnel_account_routing_observed_2024_avoided` | SAR_ADVISORY_FUNNEL_ACCOUNT |

### Group 2 — v4-new, 5 edits (typology-coverage expansion)

| Persona | Event added | New typology surfaced |
|---|---|---|
| rem_010 Ricardo (D→B) | `money_mule_recruitment_approach_dominican_2024_declined` | SAR_ADVISORY_COVID19_IMPOSTER_SCAMS |
| rem_007 Raymart | `covid_stimulus_impersonation_scam_attempted_2021` | SAR_ADVISORY_COVID19_IMPOSTER_SCAMS |
| unb_003 Shaniqua | `unauthorized_ach_greendot_prepaid_2024_reversed` | SAR_ADVISORY_THIRD_PARTY_PAYMENT_PROCESSORS |
| unb_009 Darius | `kyc_circumvention_bodega_observed_2024` | FTA_IDENTITY_2024_T5 (Circumventing Standards) |
| gig_008 Maria Soto (D→B) | `false_chargeback_rover_client_2024_disputed` | FTA_IDENTITY_2024_T12 (False Claims) |

### Grade distribution achieved

| Archetype | A | B | C | D |
|---|---:|---:|---:|---:|
| Remittance | 16.7% | 41.7% | 41.7% | 0% |
| Gig Worker | 0% | 41.7% | 41.7% | 16.7% |
| Unbanked | 0% | 100% | 0% | 0% |
| ITIN | 8.3% | 50% | 8.3% | 33.3% |

Overall D-share dropped from 20.8% (v3) to 12.5% (v4). A-share is unchanged
at 6.3% — no ethnographic sources added for gig or unbanked. Closing the A
gap remains future work.

---

## Stage 3 — V4 generator

`src/personas_v4/tabddpm_v4_generator.py` is a copy of the v3 generator with
two functional changes:

### Change 1 — Typology resolver prefers SAR

```python
# SAR advisories first — more specific, FIN-YYYY-A### citeable source.
for code, entry in TYPOLOGY.items():
    if code.startswith("SAR_"):
        for vec in entry.get("applies_to_fraud_vectors", []):
            _FRAUD_VECTOR_TO_CODE.setdefault(vec.lower(), code)
for code, entry in TYPOLOGY.items():
    if code.startswith("FTA_"):
        for vec in entry.get("applies_to_fraud_vectors", []):
            _FRAUD_VECTOR_TO_CODE.setdefault(vec.lower(), code)
```

Impact: `bec`, `ato`, `phishing`, `disaster_relief_scam` route to their
specific SAR advisory instead of the broader FTA identity code. FTA T6, T9,
T11 become "shadowed" — not an error, just more-specific codes winning.

### Change 2 — Nine new fraud-event patterns

Added to `FRAUD_EVENT_PATTERNS` so the regex parse of
`family_crisis_history` strings catches the new vocabulary:

```python
(r"ivts|hawala|informal[_ ]courier|informal[_ ]merchant", "ivts"),
(r"funnel[_ ]account|structured[_ ]deposit", "funnel_account"),
(r"hurricane[_ ]|disaster[_ ]aid|fake[_ ]charity|relief[_ ]scam", "disaster_relief_scam"),
(r"phishing|cyber[_ ]incident", "phishing"),
(r"money[_ ]mule", "money_mule"),
(r"lax[_ ]kyc|kyc[_ ]circumvention", "lax_kyc"),  # T5-only, separated from unlicensed_msb
(r"unlicensed[_ ]msb", "unlicensed_msb"),
(r"false[_ ]chargeback|false[_ ]claim", "false_chargeback"),
(r"covid[_ ]stimulus|covid[_ ]imposter|fake[_ ]government|stimulus[_ ]impersonation", "fake_government_official"),
(r"unauthorized[_ ]ach|payment[_ ]processor[_ ]fraud", "unauthorized_ach"),
```

Note that `lax_kyc` was separated from `unlicensed_msb` because only T5 lists
`lax_kyc` in its `applies_to_fraud_vectors`; `unlicensed_msb` is in both T5
and SAR_IVTS and thus routes to SAR_IVTS under the preference rule.

### Sampling logic unchanged

Everything else in the generator — joint platform→hour→amount sampling,
five v2 tightening rules (loss-tolerance cap, tight hour jitter, realistic
fees, cadence-derived txn_count_30d, tenure-derived account_age),
per-persona allocation — is bit-identical to v3.

---

## Stage 4 — Narrative fill (combined 20k Adaption job)

The original plan was to overlay v3 narratives by `persona_id` for zero credit
spend. A 50-row MVP fill on `remittance` (`adapted_output_phase2_mvp50.jsonl`)
showed that fresh per-row narratives recovered the row-level signals overlay
sacrificed (amount, hour, day, instrument). Based on that signal, the full
20,000-row submission ran as a single combined Adaption job.

`src/personas_v4/adaptive_v4.py --combined --submit/--check/--download` drives
the flow:

1. Build a single upload JSONL combining all four archetype prompt sets at
   `datasets_v4/adaptive_combined/for_adaption.jsonl`.
2. Submit one job to Adaption (one queue position vs four).
3. Download → split per `archetype` field → merge `narrative_text` into each
   archetype's `transactions_adapted.parquet` by `data_uuid`.

### Prompt structure

Each prompt embeds the persona summary, the transaction JSON, the assigned
language code, and an emotional-beat instruction:

```
Write a realistic first-person narrative (3-5 sentences) from this persona
describing a {legitimate|fraudulent} transaction that just occurred. Use the
persona's voice, cultural context, and primary language. If fraudulent, hint
at the scam mechanic without naming it explicitly.

Persona ({archetype}): {summary}

Transaction: {amount, fee, instrument, fraud_vector, hour, day, days_since_last, is_fraud}

Language to write in: {ISO-639-1 code}. Include one emotional beat consistent
with the transaction (relief, worry, gratitude, shame, obligation). Return
just the narrative text, no preamble.
```

### Outcome

- **Adaption quality**: graded by Adaption's own evaluation
- **Empties**: 47 rows initially returned empty (later refilled in v4.1; 39 remain)
- **Languages**: 20 distinct tagged languages, 92.8% tag↔detect match rate

### Stage 4b — Post-processing: prompt-tag leakage strip

About 5.8% of returned narratives (1,235 rows) contained the
"Additional Context Tags" block (archetype + persona_id + data_uuid +
is_fraud + language) echoed into the completion body — Adaption's
prompt-rephrase pipeline leaking the upload metadata into the output.

`src/personas_v4/strip_prompt_leakage.py` removes these by anchoring on
`data_uuid` (a 36-char UUID never appears in real prose) and trimming
backward through any preceding separator tokens. Run once, in place. After
the strip, no row contains `data_uuid` anywhere in `narrative_text`.

### Comparison against the abandoned overlay path

| Signal | overlay (planned) | combined fresh fill (shipped) |
|---|---:|---:|
| Corridor keyword | 71.1% | 68.4% |
| Platform name | 43.2% | 41.6% |
| Day of week | 24.5% | **43.6%** |
| Instrument | 22.7% | **37.6%** |
| Amount rounded | 7.8% | **27.4%** |
| Amount exact | 1.6% | **19.1%** |
| Hour class | 22.5% | **38.4%** |
| Language tag↔detected | 59.3% | **92.8%** |

Row-level signals roughly doubled vs the overlay would have delivered.

---

## Stage 5 — Exports and HF layout

`src/personas_v4/export_dataset.py` produces seven bundle files:

```
datasets_v4/exports/
    transactions_v4_20k.parquet    (20,000 rows, 25 columns)
    transactions_v4_20k.csv        (CSV mirror)
    personas_all.json              (46 personas, nested archetype groups)
    sources.json                   (13-entry citation registry)
    typology_registry.json         (25 typology codes)
    dataset_card.md                (HF-style card)
    coverage.json                  (per-archetype narrative fill rates)
```

`datasets_v4/huggingface/data/` has 8 HuggingFace-compatible configs:
`all`, `remittance`, `gig_worker`, `unbanked`, `itin`, `personas`, `sources`,
`typology_registry`. Each ships a single `train.parquet`.

---

## Stage 6 — v4.1 patch layer

After v4 closed at 18/25 typology coverage with the combined fresh fill,
a small patch layer brought it to 25/25 + cleaned residual issues:

- Re-stamp shadowed FTA codes (T4/T6/T9/T11) on a half-cap subset so the
  SAR counterparts persist alongside (18 → 22 codes, no Adaption credits).
- Add 3 truly-missing typology codes (T7 Abuse of Access, T8 Refusal to
  Cooperate, SAR_HUMAN_TRAFFICKING) via persona-event additions on
  unb_001, gig_001, itin_010 + 300 synthetic transactions narrated by
  Adaption (22 → 25, ~4 credits).
- Refill 51/52 empty narratives via prompt-preserving re-submit.

See `v4_1/ARCHITECTURE.md` for details. Bundle grew from 20,000 to 20,300
rows. After v4.1 the dataset ships at 25/25 typology coverage.

A separate **CoT reasoning dataset** (3,926 rows: all fraud + matched
non-fraud) was generated for SFT use; it lives at
`datasets_v4/reasoning/cot_dataset.parquet` and is independent of the
20k bundle.

---

## File map

```
src/personas_v4/
    _apply_persona_edits.py          one-shot edit script (16 edits)
    adaptive_v4.py                   narrative fill (per-archetype + --combined)
    analyze_narratives.py            5-question analysis report generator
    export_dataset.py                bundle exporter
    extract_fdic_unbanked.py         cross-references v3 FDIC bundle
    lint_personas.py                 source + typology integrity check
    overlay_v3_narratives.py         v3→v4 narrative inheritance (legacy; superseded)
    strip_prompt_leakage.py          post-process: strip echoed tag block from narratives
    tabddpm_v4_generator.py          generator with SAR-preference + expanded patterns
    # v4.1 patch layer:
    v4_1_restamp_shadowed.py         flips SAR-stamped rows to FTA equivalents
    v4_1_add_missing_typologies.py   patches 3 personas + synthesises 300 rows
    v4_1_adaption_job.py             submits combined v4.1 Adaption run
    v4_1_merge_missing.py            merges v4.1 narratives back into bundle
    build_v4_1_reprompt.py           builds the empties-refill JSONL
    # CoT subset:
    build_cot_job.py                 selects fraud + matched negatives, builds prompts
    cot_adaption_job.py              submit/check/download wrapper for the CoT job

datasets_v4/
    sources/                         (copied from v3, with unbanked archetype extension)
    {archetype}/
        personas/persona_profiles.json     synthesised personas w/ v4 edits
        synthetic/transactions.parquet     v4 generator output
        adaptive/transactions_adapted.parquet   final fresh-narrative artifact
    adaptive_combined/               combined 20k Adaption run inputs/outputs
    reasoning/                       CoT dataset (3,926 rows)
    v4_1/                            v4.1 patch layer artifacts
    exports/                         bundled deliverable (20,300 rows post-v4.1)
    huggingface/
        data/                        8 HF-compatible configs
        README.md                    HF dataset card
    ARCHITECTURE.md                  this document
    DISTRIBUTION_METRICS.md          v4 sampling + grade/typology metrics
    README.md                        directory overview + quick start
```

---

## Credit budget

| Stage | Credits |
|---|---:|
| V4 persona edits | 0 |
| V4 generator regeneration | 0 |
| Combined 20k Adaption narrative fill | ~199 |
| Phase 2 MVP narrative fill (50-row remittance only, validated approach) | ~1 |
| Post-process: prompt-tag leakage strip | 0 |
| **v4 close** | **~200** |
| v4.1 missing-typology + empties refill | ~4 |
| CoT reasoning job (3,926 rows) | (separate budget; A-graded) |

---

## Known limitations

1. **39 empty narratives remain** (~0.19% of 20,300 rows) after the v4.1 refill pass.
2. **No Forge integration yet** — Adaption's Forge unstructured-document pipeline is a possible future extension; v4 is the pre-Forge baseline.
3. **No ethnographic A-grade sources added** — A-share unchanged from v3 (6.3% overall). Closing requires UC Berkeley Labor Center / CFPB focus-group / Treasury IG interview sources.
4. **Two FTA codes (T6, T11) live alongside their SAR counterparts** as a result of the v4.1 half-cap re-stamp — both codes retain rows so coverage stays at 25/25 without erasing the SAR-preference outcome.
