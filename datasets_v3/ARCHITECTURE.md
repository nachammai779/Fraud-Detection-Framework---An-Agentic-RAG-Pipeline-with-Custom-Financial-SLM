# V3 Citation-Grounded Dataset Pipeline — Architecture Walkthrough

## Why V3

V2 generated personas from design assumptions. Corridors, fraud vectors, income
ranges, documentation-status labels — all were authored by hand (or
LLM-expanded from an authorial schema). The v2 dataset is internally coherent
but not citable: reviewers cannot check whether "Jean-Baptiste, Brooklyn
construction laborer sending to Port-au-Prince via CAM Transfer" reflects real
Haitian-diaspora remittance patterns.

V3 grounds every load-bearing persona field in a **real-world source** —
FinCEN typology advisories, FDIC microdata, Inter-American Dialogue corridor
reviews, Menjívar et al.'s TPS survey, Del Real's Venezuelan-migration
interviews, Remitly's 10-K, etc. Each persona carries a **citation registry**,
each fraud vector carries a **FinCEN typology reference**, and each row
carries a **behavioral-evidence grade** (A-D) describing the quality of the
evidence behind its persona.

V3 **does not replace** v2's synthetic generation pipeline. Generation
machinery (Tab-DDPM-style sampling, Adaption Labs narrative fill, persona-
coherence scoring) is identical. Only the conditioning *input* changes — from
authored personas to source-grounded personas.

---

## Pipeline Delta (v2 → v3)

```
V2:  persona_profiles (authored) -> Adaption Expand-World -> conditioning_schema
         -> TabDDPM v2 generator -> transactions.parquet -> narrative fill
         -> coherence verify

V3:  sources.json + extracts -> synthesised persona_profiles (with per-field grounding)
         -> TabDDPM v3 generator [PLATFORM_DB stand-in for Expand-World]
         -> transactions.parquet (+ 3 new columns)
         -> narrative fill (persona-anchored prompts)
         -> [optional] Expand-World as document-only artifact
```

Three universal columns are added to every row:

| Field | Type | Origin |
|---|---|---|
| `persona_source_ids` | list[str] | persona-level, propagated to every row of that persona |
| `behavioral_evidence_grade` | categorical A/B/C/D | persona-level, propagated |
| `fraud_vector_typology_ref` | string (nullable) | row-level, resolved from `typology_registry.json` at generation time; null when `is_fraud == 0` |

---

## Stage 1 — Source Curation

**Directory**: `datasets_v3/sources/`

- `pdfs/{archetype}/` — 7 PDFs routed by primary archetype (FinCEN FTA Identity, Remitly 10-K, Wise Remittances, Menjívar TPS, Del Real Venezuelan legalization, Vallas & Schor gig economy)
- `pdfs/hh2023/` — FDIC 2023 Household Survey full release (instrument + technical docs + codebook + 309 MB microdata CSV; microdata gitignored)
- `links/links.md` — 5 link sources (FinCEN SAR Key Terms, Oxfam America, Inter-American Dialogue, Fed Reserve synthetic-ID, Treasury OIG, IRS SOI)
- `sources.json` — citation registry, 13 entries: `{kind, title, authors, year, publisher, url, pdf_path, archetypes, accessed, notes}`
- `typology_registry.json` — 25 FinCEN typology codes: 14 `FTA_IDENTITY_2024_T*` from the FTA Identity PDF's Appendix 1, 11 `SAR_ADVISORY_*` curated from FinCEN's SAR Advisory Key Terms page
- `extracts/` — structured `persona_dimensions` extracts per source, 13 files

Scope rule: each source declares an `archetypes: [...]` list in `sources.json`. Personas may only cite sources where their archetype is in that list. The lint check (`src/personas_v3/lint_personas.py`) enforces this.

---

## Stage 2 — Persona Synthesis

**Directory**: `datasets_v3/{archetype}/personas/persona_profiles.json`

Each persona carries:

- All v2 persona fields (age, name, summary, archetype-specific world dimensions, income, language_mix, loss_tolerance_usd, etc.)
- `persona_source_ids`: list of citation IDs that grounded this persona
- `behavioral_evidence_grade`: single overall grade (A-D)
- `grounding`: per-field object `{value, evidence_basis, confidence: DIRECT|INFERRED|null, source_ids: [...]}` — confidence `null` + empty source_ids marks a design-assumption field

**Evidence grade rubric**:

| Grade | Evidence type |
|---|---|
| A | Direct ethnographic field-interview source (Menjívar TPS survey, Del Real Venezuelan interviews) |
| B | Regulatory typology / statistical survey (FinCEN FTA/SAR, FDIC, Treasury OIG, IRS SOI, Fed Reserve) |
| C | Industry / think-tank behavioural research (Remitly 10-K, Wise, IAD, Oxfam, Vallas & Schor) |
| D | Synthetic design assumption (no source grounding) |

**Grade distribution achieved vs. target**:

| Archetype | A (target) | A (actual) | B (target) | B (actual) | C (target) | C (actual) | D (target) | D (actual) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Remittance | 15-20% | **16.7%** | 25-30% | **25.0%** | 30-35% | **41.7%** | 15-25% | **16.7%** |
| Gig Worker | 20-25% | **0%** | 15-20% | **25.0%** | 20-25% | **41.7%** | 30-40% | **33.3%** |
| Unbanked | 25-30% | **0%** | 15-20% | **100%** | 15-20% | **0%** | 30-40% | **0%** |
| ITIN | 10-15% | **8.3%** | 35-40% | **50.0%** | 10-15% | **8.3%** | 30-40% | **33.3%** |

A-grade shortfall is uniform — no ethnographic sources were added for gig_worker or unbanked, and only one Menjívar-direct persona for ITIN. Closing the A gap requires additional sources (e.g. UC Berkeley Labor Center gig fieldwork, CFPB prepaid focus groups, IRS ITIN-filer Treasury-IG interviews). Not a blocker for v3 release.

**Total personas**: 46 (12 remittance, 12 gig_worker, 10 unbanked, 12 ITIN). Unbanked capped at 10 because FDIC joint-distribution cells start repeating past that point.

---

## Stage 3 — V3 Generator (`src/personas_v3/tabddpm_v3_generator.py`)

### Conditioning-input decision: PLATFORM_DB instead of Expand-World

V2 called Adaption's Expand-the-World step on each persona to produce 5 JSON
schema blocks (`transaction_calendar`, `remittance_cadence`,
`income_seasonality`, `device_fingerprint_evolution`,
`communication_patterns`). V3 **skips this call** and uses a hardcoded
`PLATFORM_DB` (15 platforms × hour-window × amount-band × cadence × fee) as a
stand-in for gig-worker conditioning, plus archetype defaults + persona fields
for the other three archetypes.

Reason: v3's evidence rigor comes from the persona-grounding layer (stage 2),
not from per-persona LLM-expanded schemas. `PLATFORM_DB` encodes the
industry-standard platform behavior that Expand-World would return for a gig
worker anyway. For remittance/unbanked/itin, direct persona-field sampling
(amount bands from `loss_tolerance_usd`, cadence from `remittance_cadence`,
channel from `transfer_service_loyalty`) has turned out to be sufficient.

**Expand-World remains an option** (see `datasets_v3/README.md` planned Option
A artifact) — can be produced for methodology-completeness without retriggering
regeneration.

### Sampling mechanics (ported from v2 R4)

1. **Per-persona allocation**: `5000 / n_personas` with remainder distributed.
2. **Joint path** (gig_worker): weighted platform pick → hour from platform's
   time window → amount from platform's band → cadence from platform's cadence.
   Amazon Flex at 5-9am, Uber Eats at 6-11pm, etc.
3. **Independent path** (remittance / unbanked / ITIN): hour from
   `DEFAULT_HOUR_RANGES[archetype]`, amount lognormal within archetype band,
   cadence from persona-derived `sub_cadences`, channel from
   `transfer_service_loyalty` / archetype defaults.
4. **Five v2 tightening rules** applied throughout:
   - Loss-tolerance cap: `amount_legit ≤ loss_tolerance_usd × 1.1`
   - Tight hour jitter (σ=0.3 joint, 0.5 independent), fraud shift ±3-4h
   - Realistic fees (platform-stated or archetype default; not % of amount)
   - Cadence-derived `txn_count_30d` via Poisson(30/avg_cadence)
   - Tenure-derived `account_age_days` with 15% gaussian jitter

### V3-specific additions

- **Per-persona fraud-vector weighting**: `family_crisis_history` parsed
  for documented fraud events (e.g., `tech_support_scam_attempted_2024` →
  `tech_support_scam`), which are weighted 2× over archetype defaults.
  Result: Priya's fraud rows skew toward tech-support; Marcus's toward ATO;
  Carmen's toward grandparent/ICE.
- **Typology resolution**: `fraud_vector` (for fraud rows) is looked up in
  `typology_registry.json` to populate `fraud_vector_typology_ref`. Null for
  legitimate rows.
- **3 new columns** propagated to every row (see table above).

---

## Stage 4 — Adaption Narrative Fill (`src/personas_v3/adaptive_v3.py`)

Same shape as v1/v2 — JSONL upload → Adaption run → poll → download → merge.

**Prompt structure** (v3 upgrade): full persona summary carried forward, not
just key-value pairs. The prompt includes:

- Full persona summary (grounded biographical details propagate)
- Transaction dict (amount, fee, instrument, hour, day, days_since, is_fraud)
- `fraud_vector_typology_ref` surfaced when present (Adaption sees the FinCEN
  code)
- Language directive from the row's sampled language

**Observed narrative quality** (from spot-checks on remittance / gig_worker /
unbanked):

- Biographical tells propagate: Carmen's "abuelita/mami" detection tell,
  Maria's 2025 remittance-tax, Priya's Microsoft/sari-shop, rem_009
  Kwame's Bronx-merchant-plus-Wise hybrid.
- Fraud mechanics are hinted without being named.
- Non-English languages produced natively (Marathi, Amharic, Yoruba, Twi,
  Russian, Vietnamese, Spanish — in native script).

**Credit cost**: v2 experience was ~1 credit per 50 rows. For a full 5000-row
fill across 4 archetypes, expect ~400 credits. Stalled queue during the
2026-04-21 submission was resolved by Adaption's team.

---

## Stage 5 — [Optional] Expand-World as Methodology Artifact

Not yet run. If run later, produces per-persona conditioning schemas that ship
as a documentation artifact (not fed back into generation). Cost: ~4 credits,
~45 min. Location: `datasets_v3/{archetype}/expanded_world/conditioning_schema.parquet`.

---

## Stage 6 — [Optional] Coherence Verification

Not yet run. Mirrors v2's `persona_verify.py` — sample 50 rows per archetype,
ask Adaption to score behavioural coherence of each row against its persona,
threshold `< 0.6` for flag-for-regen. Cost: ~4 credits.

Target: beat v2 R4's 0.581 overall mean. Expected easily — grounded personas
produce tighter transaction-to-persona alignment than authored ones.

---

## Distribution Metrics

See `datasets_v3/DISTRIBUTION_METRICS.md` for the v3-specific additions (grade
distribution, typology coverage, per-persona fraud-weighting effect). The
baseline v1/v2 distribution mechanics document lives at
`datasets_v2/DISTRIBUTION_METRICS.md` and is still relevant — v3 inherits all
of that.

---

## File Map

```
src/personas_v3/
    extract_fdic_unbanked.py         microdata → empirical distributions
    lint_personas.py                 sources + typology integrity check
    tabddpm_v3_generator.py          v3 generator (joint sampling + 3 new cols)
    adaptive_v3.py                   narrative fill (--estimate/--submit/--check/--download)
    export_dataset.py                export bundle assembly

datasets_v3/
    sources/
        pdfs/{archetype}/*.pdf       7 PDFs organised by primary archetype
        pdfs/hh2023/                 FDIC microdata bundle (mostly gitignored)
        links/links.md               7 URLs
        extracts/*.json              13 structured extracts (persona_dimensions)
        sources.json                 13-entry citation registry
        typology_registry.json       25 FinCEN typology codes
    {archetype}/
        personas/persona_profiles.json       synthesised personas w/ grounding
        synthetic/transactions.parquet       TabDDPM v3 output (22 columns)
        adaptive/for_adaption.jsonl          upload payload
        adaptive/adapted_output.jsonl        Adaption raw output
        adaptive/transactions_adapted.parquet  merged final 25-column artifact
        adaptive/run_metadata.json           most-recent job metadata
    exports/
        transactions_v3_20k.parquet  combined 20k-row dataset
        transactions_v3_20k.csv      CSV version
        personas_all.json            46 personas, flat, with grade distribution
        sources.json                 snapshot of the registry
        typology_registry.json       snapshot of typology codes
        dataset_card.md              HF-style dataset card
        coverage.json                per-archetype narrative-fill coverage
    adaptive_jobs.json               Adaption job tracker (ledger)
    ARCHITECTURE.md                  this document
    DISTRIBUTION_METRICS.md          v3 distribution-metrics doc (see separately)
```

---

## Credit Budget (observed + planned)

| Stage | Credits (actual / estimated) |
|---|---:|
| v3 narrative fill — remittance (5000 rows) | ~100 (completed) |
| v3 narrative fill — gig_worker (5000 rows) | ~100 (completed) |
| v3 narrative fill — unbanked (5000 rows) | ~100 (completed) |
| v3 narrative fill — ITIN (5000 rows) | ~100 (in progress) |
| **Narrative-fill subtotal** | **~400** |
| Expand-World (optional) | ~4 |
| Coherence verify (optional) | ~4 |
| **Grand total** | **~408** |

---

## Known Limitations

1. **No ethnographic A-grade sources for gig_worker / unbanked**. Mitigation:
   document as future-work in the paper.
2. **PLATFORM_DB is curated, not empirically validated**. Closes much of the
   Expand-World gap but reviewers may object. Mitigation: Option-A artifact
   (run Expand-World once for documentation, 4 credits).
3. **FTC Consumer Sentinel** was dropped from sources.json due to web-fetch 403
   block. Re-add by downloading the PDF manually if needed for fraud-scale
   grounding.
4. **IRS SOI landing page** only — no drill-down Pub 1304 tables fetched.
   Mitigation: additional extraction pass if needed.
5. **FDIC microdata** (309 MB) is kept locally and gitignored; analytic CSV
   must be re-downloaded from FDIC for anyone wanting to reproduce the
   extraction. Citation details in `sources.json` include the URL.
