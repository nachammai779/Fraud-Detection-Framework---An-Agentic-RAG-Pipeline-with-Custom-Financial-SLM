# V4 Citation-Grounded Dataset Pipeline — Architecture Walkthrough

## What changed from v3

V3 shipped a citation-grounded dataset with 10 of 25 FinCEN typology codes
exercised. V4 closes that coverage gap through three targeted changes, none
of which required new Adaption credits.

| Change | Effect |
|---|---|
| 16 persona edits (11 carried from a v3 draft + 5 new typology-focused) | Documented fraud events expanded across gig_worker, remittance, and unbanked personas; 8 persona grade upgrades (D→B) |
| Typology resolver rule: SAR advisories preferred over FTA codes when both match a fraud_vector | Surfaces 4 previously-shadowed SAR advisory codes (ATO, BEC, Cyber Events, Disaster-Related Fraud) in every fraud row |
| 9 new fraud-event regex patterns in the generator | New events like `hurricane_maria_fake_charity_scam_attempted_2018`, `ivts_ghanaian_merchant_network_recurring`, and `unauthorized_ach_greendot_prepaid_2024_reversed` map to the correct typology code at sampling time |
| Narrative overlay from v3 per `persona_id` | v4 transactions inherit v3's Adaption-filled narrative_text without new credit spend; accepts row-level drift in amounts / days / languages (see tradeoff section) |

**Typology coverage: 10 → 18 of 25 codes exercised (+80% relative).**

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
     -> Overlay v3 narratives by persona_id -> transactions_adapted.parquet
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

## Stage 4 — Narrative overlay (v3 → v4)

`src/personas_v4/overlay_v3_narratives.py` copies narrative_text from v3's
`transactions_adapted.parquet` files to v4's rows, matched by `persona_id`.
For each v4 row, a v3 row with the same persona is chosen at random
(seeded) and its narrative is copied.

### Why overlay instead of new narrative fill

- **Cost**: 0 credits vs ~400 credits for a full 20,000-row fresh narrative fill.
- **Persona voice preserved**: narratives remain biographically consistent with
  the persona (same corridor, platform, family context).
- **Explicit tradeoff accepted**: row-level grounding drifts — a v4 row might
  have `language=es` but the overlaid narrative is in English (from a
  different v3 row of the same persona). Amount / day / hour details in the
  narrative reflect the source v3 row, not the new v4 row.

### Measured drift (from `analyze_narratives.py` on v4)

| Signal | v3 propagation | v4 propagation | Notes |
|---|---:|---:|---|
| Corridor keyword | 71.4% | 71.1% | persona-level, carries cleanly |
| Platform name | 42.7% | 43.2% | persona-level, carries cleanly |
| Persona first name | 1.4% | 1.4% | stable (first-person narrative rarely self-names) |
| Day of week | 47.4% | 24.5% | row-level drift |
| Instrument | 37.7% | 22.7% | row-level drift |
| Amount rounded | 35.9% | 7.8% | heavy row-level drift |
| Amount exact | 28.5% | 1.6% | heavy row-level drift |
| Hour class | 35.9% | 22.5% | row-level drift |
| Language tag↔detected match | 92.1% | 59.3% | drift from per-row language resampling vs per-persona narrative pool |

If row-level narrative fidelity matters downstream (e.g. for training a model
to predict amount from narrative), a v4.1 fresh narrative pass is the fix.
Phase 2 (planned) submits 50 rows per archetype for an MVP-sized
sample of fresh v4 narratives to measure whether the quality-uplift
justifies a full resubmission.

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

## Stage 6 — Phase-2 narrative uplift (planned, next)

The overlay tradeoff is accepted but not ideal. Phase 2 submits a
stratified **50 rows per archetype × 4 archetypes = 200 rows** to Adaption
for fresh narrative fill, then compares row-level propagation rates between
v4-overlay and v4-fresh narratives to decide whether a full 20k fresh pass is
worthwhile.

**Estimated cost**: ~4 credits (1 credit per 50-row archetype at v3-era
pricing).

**Success criterion**: if v4-fresh shows amount-in-narrative propagation
recover to ≥30% (close to v3's 35.9%), a full resubmission is justified.
Otherwise the overlay is sufficient for v4's use cases.

---

## File map

```
src/personas_v4/
    _apply_persona_edits.py          one-shot edit script (16 edits)
    adaptive_v4.py                   narrative fill (--estimate/--submit/--check/--download)
    analyze_narratives.py            5-question analysis report generator
    export_dataset.py                bundle exporter
    extract_fdic_unbanked.py         cross-references v3 FDIC bundle
    lint_personas.py                 source + typology integrity check
    overlay_v3_narratives.py         v3→v4 narrative inheritance
    tabddpm_v4_generator.py          generator with SAR-preference + expanded patterns

datasets_v4/
    sources/                         (copied from v3, with unbanked archetype extension)
    {archetype}/
        personas/persona_profiles.json     synthesised personas w/ v4 edits
        synthetic/transactions.parquet     v4 generator output
        adaptive/transactions_adapted.parquet   v3 narrative-overlaid final artifact
    exports/                         bundled deliverable
    huggingface/
        data/                        8 HF-compatible configs
        README.md                    HF dataset card
    ARCHITECTURE.md                  this document
    DISTRIBUTION_METRICS.md          v4 sampling + grade/typology metrics
```

---

## Credit budget

| Stage | Credits |
|---|---:|
| V4 persona edits | 0 |
| V4 generator regeneration | 0 |
| V3 narrative overlay | 0 |
| V4 export + HF build | 0 |
| Phase 2 MVP narrative fill (planned, next commit) | ~4 |
| **Total v4 spend so far** | **0** |

All v4 quality uplift to this point was free. Phase 2 is the first and
smallest credit spend for v4 — bounded at ~4 credits to validate fresh
narrative uplift before committing to a larger pass.

---

## Known limitations

1. **Narrative row-level drift** — quantified in Stage 4, deliberate tradeoff.
2. **7 unexercised typology codes** — 5 are FTA/SAR shadow-dedupes (same fraud routed to the more-specific code), 1 insider concept (T7), 1 deliberately skipped (SAR_HUMAN_TRAFFICKING).
3. **No Forge integration yet** — Adaption's Forge unstructured-document pipeline is the next major extension; v4 is the pre-Forge baseline.
4. **No ethnographic A-grade sources added** — A-share unchanged from v3 (6.3% overall). Closing requires UC Berkeley Labor Center / CFPB focus-group / Treasury IG interview sources.
