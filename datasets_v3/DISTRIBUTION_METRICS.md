# Distribution Metrics in v3

v3 inherits all the sampling mechanics of v2 (joint platform→hour→amount for
gig_worker, archetype defaults + persona fields for the other three
archetypes, five v2 tightening rules). The baseline v1/v2 distribution
mechanics are documented in `datasets_v2/DISTRIBUTION_METRICS.md` — still
relevant.

This document records **v3-specific additions**.

---

## 1. What changed on the distribution side

| Dimension | v2 behaviour | v3 behaviour |
|---|---|---|
| Per-persona conditioning | Adaption-expanded schemas (5 JSON blocks) | hardcoded `PLATFORM_DB` + archetype defaults + persona fields |
| Fraud-vector weighting | Archetype-uniform | **Per-persona weighted** via `family_crisis_history` parsing |
| Typology reference | Not present | `fraud_vector_typology_ref` resolved from `typology_registry.json` |
| Persona evidence grade | Not present | `behavioral_evidence_grade` per persona |
| Citation attribution | Not present | `persona_source_ids` per persona |

Core Tab-DDPM-style lognormal/uniform/Poisson sampling for amounts, hours,
cadence is unchanged from v2 R4.

---

## 2. Per-persona fraud-vector weighting

The v3 generator parses each persona's `family_crisis_history` for documented
fraud events and up-weights those vectors 2× over archetype defaults.

### Implementation

```python
FRAUD_EVENT_PATTERNS = [
    (r"phone_scam",              "phone_scam"),
    (r"irs[_ ]impersonat",       "irs_impersonation"),
    (r"fake_ice_call",           "fake_ICE_call"),
    (r"tech[_ ]support[_ ]scam", "tech_support_scam"),
    (r"romance[_ ]scam",         "romance_scam"),
    (r"whatsapp[_ ]impersonat",  "whatsapp_impersonation"),
    (r"grandparent[_ ]scam",     "grandparent_scam"),
    ...
]
# Matching events get weight 2.0; archetype defaults get weight 1.0
# Probabilities normalised across the union, then used in rng.choice()
```

### Observed effect (remittance, from generated rows)

| Persona | Documented fraud event | Dominant fraud vector in generated fraud rows |
|---|---|---|
| rem_005 Priya | `tech_support_scam_attempted_2024` | **tech_support_scam 13/43** (30 %) |
| rem_006 Maria | `fake_ICE_call_attempted_2023` | **fake_ICE_call 9/38** (24 %) |
| rem_008 Yosef | `phone_scam_IRS_impersonation_2024` | **irs_impersonation-adjacent dominant** |
| rem_011 Carmen | `grandparent_scam_attempted_2024` | **grandparent_scam 8/45** (18 %, only this persona) |
| gig_009 Tyler | synthetic-ID attack 2024 | **synthetic_id 10/38** (26 %) |
| gig_011 Marcus | ATO via credential stuffing | **ato 8/32** (25 %) |

Without the weighting, each archetype default fraud vector would appear at
roughly `1 / n_defaults` rate for every persona's fraud rows. The weighting
concentrates each persona's fraud rows on its documented exposure, creating
a cleaner per-persona-fraud-pattern signal for downstream ML.

---

## 3. Typology coverage metric

`fraud_vector_typology_ref` is populated for every fraud row (is_fraud=1) and
null for every legitimate row. Observed over the combined 20k-row output:

| Archetype | Fraud rate | Typology fill rate (= fraud rate) |
|---|---:|---:|
| remittance | 9.9% | 9.9% |
| gig_worker | 10.4% | 10.4% |
| unbanked | 11.0% | 11.0% |
| itin | 9.7% | 9.7% |

### Typology distribution (remittance, fraud rows)

```
FTA_IDENTITY_2024_T10 (Scam)           337 rows
FTA_IDENTITY_2024_T1  (General Fraud)  157 rows
```

Remittance fraud maps heavily to T10 (Scam) because most remittance-persona
fraud vectors are imposter / social-engineering schemes (phone_scam,
romance_scam, fake_ICE_call, whatsapp_impersonation). A smaller share maps to
T1 (General Fraud) for unauthorised-wire events.

**Typology mapping coverage**: 72 unique `fraud_vector` strings registered in
`typology_registry.json` across 25 typology codes (14 FTA Identity + 11 SAR
Advisory). Unmapped vectors fall back to `FTA_IDENTITY_2024_T1` (General
Fraud) — none in the current v3 output.

---

## 4. Grade distribution as a dataset-quality metric

Every row carries the `behavioral_evidence_grade` of its source persona.
Aggregated over the dataset, the grade distribution is a **dataset-quality
metric**:

| Grade | Meaning | v3 share (observed) |
|---|---|---:|
| A | Direct ethnographic field interview | **6.3 %** |
| B | Regulatory typology (FinCEN / FDIC / Treasury) | **50.0 %** |
| C | Industry / think-tank research (Remitly / Wise / IAD / V&S) | **22.9 %** |
| D | Synthetic design assumption | **20.8 %** |

### Per-archetype breakdown

| Archetype | A | B | C | D |
|---|---:|---:|---:|---:|
| Remittance | 16.7% | 25.0% | 41.7% | 16.7% |
| Gig Worker | 0% | 25.0% | 41.7% | 33.3% |
| Unbanked | 0% | 100% | 0% | 0% |
| ITIN | 8.3% | 50.0% | 8.3% | 33.3% |

See `datasets_v3/ARCHITECTURE.md` for target distributions and gap analysis.

**Dataset-level implication**: downstream consumers can filter by grade for
higher-evidence subsets (e.g., `grade in ['A','B']` → 56.3% of rows with
regulatory-or-better backing). Useful for publications or fairness audits
where evidence provenance matters.

---

## 5. What v3 still doesn't compute

Consistent with v1/v2:

- **No synthetic-vs-seed marginal comparison** (generator sampling spec is
  the ground truth by construction).
- **No statistical divergence tests** (KL / Wasserstein / chi-sq) on column
  marginals.
- **No per-column flagging** (flagging is done via persona_verify coherence
  scoring, which is row-level not column-level).
- **No narrative-quality metric** beyond subjective inspection.

Future-work options identical to v2's (see `datasets_v2/DISTRIBUTION_METRICS.md`
§4 "Suggested future metrics").

---

## 6. File map (distribution-relevant)

```
datasets_v3/sources/typology_registry.json    25 FinCEN codes, fraud_vector → code mapping
datasets_v3/sources/sources.json              citation registry (archetype-scoped)
datasets_v3/{archetype}/personas/persona_profiles.json
    └── each persona has `grounding` object with per-field evidence_basis + confidence
datasets_v3/{archetype}/synthetic/transactions.parquet
    └── 22-col output including the 3 v3 columns
datasets_v3/{archetype}/adaptive/transactions_adapted.parquet
    └── 25-col output after Adaption narrative fill
datasets_v3/exports/transactions_v3_20k.parquet    combined deliverable
src/personas_v3/tabddpm_v3_generator.py       generator (per-persona fraud weights + joint sampling)
src/personas_v3/lint_personas.py              source + typology integrity check
```
