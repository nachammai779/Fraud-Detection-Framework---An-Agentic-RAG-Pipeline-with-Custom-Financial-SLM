# Distribution Metrics in v4

v4 inherits all sampling mechanics from v3 unchanged (joint platform→hour→amount
for gig_worker, archetype defaults + persona fields for the other three, five
v2 tightening rules). The v1/v2 baselines remain documented in
`datasets_v2/DISTRIBUTION_METRICS.md`; the v3 layer in
`datasets_v3/DISTRIBUTION_METRICS.md`.

This document records **v4-specific additions and shifts**.

---

## 1. What changed on the distribution side

| Dimension | v3 behaviour | v4 behaviour |
|---|---|---|
| Per-persona conditioning | hardcoded PLATFORM_DB + archetype defaults | unchanged |
| Fraud-vector weighting | per-persona via family_crisis_history | **expanded** — 9 new regex patterns catch IVTS, funnel-account, hurricane, phishing, money-mule, lax-KYC, unlicensed-MSB, false-chargeback, COVID-imposter, unauthorized-ACH |
| Typology resolver | first match in registry order (FTA first) | **SAR advisory preferred** over FTA when both match |
| Persona grade distribution | 6.3 A / 50 B / 22.9 C / 20.8 D | 6.3 A / **58.3 B** / 22.9 C / **12.5 D** |
| Narrative source | Adaption-filled per row | v3 overlay by persona_id (row-level drift accepted) |

---

## 2. Typology coverage: 10 → 18 of 25 codes exercised

v3 had 10 codes in production output. v4 has **18**. Net additions:

| Code | v3 rows | v4 rows | Trigger |
|---|---:|---:|---|
| SAR_ADVISORY_ELDER_FINANCIAL_EXPLOITATION | 337 | 326 | (already in v3) |
| SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD | 0 | **271** | SAR-preference + gig_001 SIM-swap + gig_011 ATO |
| FTA_IDENTITY_2024_T1 (General Fraud) | 276 | 259 | — |
| FTA_IDENTITY_2024_T10 (Scam) | 566 | 207 | redirected to SAR-specifics |
| SAR_ADVISORY_TAX_REFUND_FRAUD | 205 | 205 | — |
| FTA_IDENTITY_2024_T13 (Synthetic Identity) | 212 | 197 | — |
| FTA_IDENTITY_2024_T2 (False Records) | 102 | 101 | — |
| FTA_IDENTITY_2024_T3 (Identity Theft) | 204 | 95 | — |
| SAR_ADVISORY_BEC_FRAUD | 0 | **88** | SAR-preference + gig_004/gig_006 BEC events |
| FTA_IDENTITY_2024_T14 (Kiting) | 87 | 86 | — |
| SAR_ADVISORY_IVTS | 0 | **29** | rem_004 + rem_009 IVTS/hawala events |
| SAR_ADVISORY_COVID19_IMPOSTER_SCAMS | 0 | **25** | rem_007 + rem_010 money-mule/COVID events |
| SAR_ADVISORY_CYBER_EVENTS | 0 | **15** | gig_012 phishing event |
| SAR_ADVISORY_THIRD_PARTY_PAYMENT_PROCESSORS | 0 | **15** | unb_003 unauthorized-ACH event |
| FTA_IDENTITY_2024_T12 (False Claims) | 0 | **13** | gig_008 false-chargeback event |
| SAR_ADVISORY_DISASTER_RELATED_FRAUD | 0 | **13** | rem_002 + rem_011 hurricane events |
| SAR_ADVISORY_FUNNEL_ACCOUNT | 0 | **11** | rem_012 funnel-account event |
| FTA_IDENTITY_2024_T5 (Circumventing Standards) | 0 | **7** | unb_009 lax-KYC event |

**Eight new typology codes exercised in v4.** Remaining 7 unexercised are
either FTA/SAR shadow-dedupes (T6, T9, T11 shadowed by their SAR
equivalents), insider concepts not applicable to personas (T7 Abuse of
Access, T8 Refusal to Cooperate), or deliberately skipped as sensitive
(SAR_HUMAN_TRAFFICKING).

T4 Third-Party Money Laundering remains recoverable — requires adding a
persona event with the `third_party_laundering` vector specifically (not
`money_mule`, which routes to SAR_COVID under the preference rule).

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

## 4. Narrative propagation drift (overlay cost)

Narrative overlay preserves persona-level grounding but **drops row-level
grounding** on ~30-80% of applicable signals:

| Signal | v3 | v4 | Δ | Category |
|---|---:|---:|---:|---|
| Corridor keyword | 71.4% | 71.1% | -0.3 pp | Persona-level, stable |
| Platform name | 42.7% | 43.2% | +0.5 pp | Persona-level, stable |
| Persona first name | 1.4% | 1.4% | 0 | Persona-level, stable |
| Day of week | 47.4% | 24.5% | **-22.9 pp** | Row-level drift |
| Instrument | 37.7% | 22.7% | **-15.0 pp** | Row-level drift |
| Amount rounded | 35.9% | 7.8% | **-28.1 pp** | Row-level drift |
| Amount exact | 28.5% | 1.6% | **-26.9 pp** | Heavy row-level drift |
| Hour class | 35.9% | 22.5% | -13.4 pp | Row-level drift |
| Language tag↔detected match | 92.1% | 59.3% | **-32.8 pp** | Row-level drift |

### Interpretation

- **Persona-level signals (corridor, platform, name) are unchanged** — the
  overlay by persona_id preserves these by design.
- **Row-level signals degrade proportionally to their specificity**:
  exact amount drops furthest (-26.9 pp), rounded amount next, then hour/day
  context. The effect is exactly what you'd expect from randomly pairing a
  row's metadata with a narrative written for a different row.

### Downstream implications

- Persona-classification models that only read `narrative_text` are
  **unaffected** — persona voice is intact.
- Amount-prediction or cadence-prediction models that try to recover
  transaction features from narrative text will see **substantially
  degraded signal**. Recommend they use the structured columns directly.
- Fraud-detection models using narrative + transaction features together
  should not be harmed — their primary signal is the fraud_vector +
  metadata, which are accurate; narrative adds persona context which is
  also accurate.

Phase 2 (planned) tests whether fresh narrative fill on 200 rows (50 per
archetype, ~4 credits) recovers the row-level signals. If yes, a full
20k-row fresh fill becomes justifiable.

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
