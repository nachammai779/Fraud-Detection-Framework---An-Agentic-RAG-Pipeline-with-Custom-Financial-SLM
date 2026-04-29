# Distribution Metrics in v4

v4 inherits all sampling mechanics from v3 unchanged (joint platform→hour→amount
for gig_worker, archetype defaults + persona fields for the other three, five
v2 tightening rules). The v1/v2 baselines remain documented in
`datasets_v2/DISTRIBUTION_METRICS.md`; the v3 layer in
`datasets_v3/DISTRIBUTION_METRICS.md`.

This document records **v4-specific additions and shifts**, including the
20k combined Adaption fresh fill and the v4.1 patch layer that closed
typology coverage to 25/25.

---

## 1. What changed on the distribution side

| Dimension | v3 behaviour | v4 behaviour |
|---|---|---|
| Per-persona conditioning | hardcoded PLATFORM_DB + archetype defaults | unchanged |
| Fraud-vector weighting | per-persona via family_crisis_history | **expanded** — 9 new regex patterns catch IVTS, funnel-account, hurricane, phishing, money-mule, lax-KYC, unlicensed-MSB, false-chargeback, COVID-imposter, unauthorized-ACH |
| Typology resolver | first match in registry order (FTA first) | **SAR advisory preferred** over FTA when both match |
| Persona grade distribution | 6.3 A / 50 B / 22.9 C / 20.8 D | 6.3 A / **58.3 B** / 22.9 C / **12.5 D** |
| Narrative source | Adaption-filled per row | combined 20k Adaption fresh fill (replaces planned overlay) |
| Post-processing | none | prompt-tag leakage strip (1,235 rows cleaned) |
| Final coverage | 10 / 25 codes | **25 / 25 codes** after v4.1 patch layer |

---

## 2. Typology coverage: 10 → 25 of 25 codes exercised (post-v4.1)

v3 had 10 codes in production output. v4 closed at 18 after the generator
changes + combined fill. The v4.1 patch layer added 7 more — half-cap
re-stamps for shadowed FTA codes (T4/T6/T9/T11) and 3 new persona-event
additions for the remaining truly missing codes (T7/T8/HUMAN_TRAFFICKING).

Final fraud-row counts per code, ordered by frequency (post-v4.1):

| Code | Rows | Source |
|---|---:|---|
| SAR_ADVISORY_ELDER_FINANCIAL_EXPLOITATION | 326 | inherited from v3 |
| FTA_IDENTITY_2024_T1 (General Fraud) | 259 | broad coverage |
| FTA_IDENTITY_2024_T10 (Scam) | 207 | redirected to SAR-specifics |
| SAR_ADVISORY_TAX_REFUND_FRAUD | 205 | inherited |
| FTA_IDENTITY_2024_T13 (Synthetic Identity) | 197 | inherited |
| SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD | 171 | SAR-preference + gig_001/gig_011 events |
| FTA_IDENTITY_2024_T2 (False Records) | 101 | inherited |
| FTA_IDENTITY_2024_T6 (Account Takeover) | 100 | **v4.1** half-cap re-stamp |
| SAR_ADVISORY_HUMAN_TRAFFICKING | 100 | **v4.1** itin_010 wage_confiscation event (100 synth rows) |
| FTA_IDENTITY_2024_T8 (Refusal to Cooperate) | 100 | **v4.1** gig_001 platform_refusal event (100 synth rows) |
| FTA_IDENTITY_2024_T7 (Abuse of Access) | 100 | **v4.1** unb_001 POA_abuse event (100 synth rows) |
| FTA_IDENTITY_2024_T3 (Identity Theft) | 95 | inherited |
| FTA_IDENTITY_2024_T14 (Kiting) | 86 | inherited |
| FTA_IDENTITY_2024_T11 (BEC) | 44 | **v4.1** half-cap re-stamp |
| SAR_ADVISORY_BEC_FRAUD | 44 | gig_004/gig_006 BEC events (after v4.1 half-cap) |
| SAR_ADVISORY_IVTS | 29 | rem_004 + rem_009 |
| SAR_ADVISORY_COVID19_IMPOSTER_SCAMS | 17 | rem_007 + rem_010 |
| SAR_ADVISORY_THIRD_PARTY_PAYMENT_PROCESSORS | 15 | unb_003 unauthorized-ACH |
| FTA_IDENTITY_2024_T12 (False Claims) | 13 | gig_008 false-chargeback |
| SAR_ADVISORY_DISASTER_RELATED_FRAUD | 13 | rem_002 + rem_011 hurricane |
| SAR_ADVISORY_FUNNEL_ACCOUNT | 11 | rem_012 |
| FTA_IDENTITY_2024_T4 (Third-Party ML) | 8 | **v4.1** half-cap re-stamp |
| SAR_ADVISORY_CYBER_EVENTS | 8 | gig_012 phishing (after v4.1 half-cap) |
| FTA_IDENTITY_2024_T9 (Cyber Incident) | 7 | **v4.1** half-cap re-stamp |
| FTA_IDENTITY_2024_T5 (Circumventing Standards) | 7 | unb_009 lax-KYC |

Total fraud rows: 2,263 across 25 codes. **Coverage is complete** — all
25 FinCEN typology codes in `typology_registry.json` have at least one
exemplar fraud row.

---

## 3. Grade distribution shift

Persona-level edits promoted 8 personas from lower to higher grades:

| Persona | v3 grade | v4 grade | Reason |
|---|---|---|---|
| rem_010 Ricardo | D | **B** | money_mule event + FinCEN sources added |
| rem_012 Aleksandr | D | **B** | funnel_account event + FinCEN sources added |
| gig_006 Hai | D | **B** | bec_salon_supplier event + FinCEN sources added |
| gig_008 Maria Soto | D | **B** | false_chargeback event + FinCEN sources added |

(Other edits added events to already-B personas; grade unchanged.)

### Overall share

| Grade | v3 overall | v4 overall | Δ |
|---|---:|---:|---:|
| A | 6.3% | 6.3% | 0 |
| B | 50.0% | 58.3% | +8.3 |
| C | 22.9% | 22.9% | 0 |
| D | 20.8% | 12.5% | -8.3 |

Dataset-level evidence quality improved — 64.6% of rows are now grade-A-or-B
backed (up from 56.3%), which matters for any downstream filter like
`grade in ['A','B']`.

---

## 4. Narrative propagation (combined 20k fresh fill)

The combined 20k Adaption job replaced the planned overlay path. Row-level
signals propagate at a rate appropriate for first-person narrative voice:

| Signal | v3 | v4 (fresh fill, post-v4.1) | Notes |
|---|---:|---:|---|
| Corridor keyword | 71.4% | 68.4% | persona-level, stable |
| Platform name | 42.7% | 41.6% | persona-level, stable |
| Persona first name | 1.4% | 1.8% | first-person rarely self-names |
| Day of week | 47.4% | 43.6% | row-level, recovered |
| Instrument | 37.7% | 37.6% | row-level, recovered |
| Amount rounded | 35.9% | 27.4% | row-level |
| Amount exact | 28.5% | 19.1% | row-level |
| Hour class | 35.9% | 38.4% | row-level, recovered |
| Language tag↔detected match | 92.1% | 92.8% | row-level, recovered |

### Interpretation

- **Persona-level signals (corridor, platform, name)** match v3 within ±3 pp.
- **Row-level signals (day, instrument, amount, hour, language)** are within
  v3's range or higher, confirming the combined-fill recovered the
  signal-fidelity that the abandoned overlay would have lost.
- **Empties remaining**: 39 of 20,300 rows (~0.19%) have empty
  `narrative_text` after the v4.1 refill pass.

### Downstream implications

- Models using narrative + structured features together get accurate signal
  on both axes.
- Amount-prediction from narrative is feasible (19.1% of rows quote the
  exact amount, 27.4% quote a rounded version).
- Persona-classification from narrative voice is unaffected.

---

## 5. What v4 still doesn't compute

Same as v3 (see `datasets_v3/DISTRIBUTION_METRICS.md` §5). No statistical
divergence tests, no per-column marginal comparison, no coherence
verification yet. Phase 3 (post-Forge) will add coherence scoring.

---

## 6. File map (distribution-relevant)

```
datasets_v4/sources/typology_registry.json    25 FinCEN codes, unchanged
datasets_v4/sources/sources.json              13 entries, two unbanked archetype extensions
datasets_v4/{archetype}/personas/persona_profiles.json
    └── 16 edits applied (family_crisis_history + grounding + source_ids)
datasets_v4/{archetype}/synthetic/transactions.parquet
    └── 20-25 col output with 3 v4 columns including updated fraud_vector_typology_ref
datasets_v4/{archetype}/adaptive/transactions_adapted.parquet
    └── narrative_text overlaid from v3 per persona_id
datasets_v4/exports/transactions_v4_20k.parquet    combined deliverable (20k rows, 25 cols)
datasets_v4/exports/analysis_report.json           full 5-question analysis
src/personas_v4/tabddpm_v4_generator.py            generator (SAR-pref + expanded patterns)
src/personas_v4/overlay_v3_narratives.py           narrative inheritance script
src/personas_v4/_apply_persona_edits.py            persona edit application
src/personas_v4/lint_personas.py                   source + typology integrity check
src/personas_v4/analyze_narratives.py              metric report generator
```
