# Distribution Metrics in v1 and v2

This document describes the distribution-sampling mechanics and the quality
metrics used to evaluate synthetic rows across the two generations of the
pipeline.

The two generators ship the same 25-column schema but use very different
*distribution strategies*:

- **v1** learns distributions from a profile-calibrated seed corpus (Tab-DDPM
  Gaussian diffusion + weighted categorical sampling).
- **v2** samples from per-persona conditioning schemas (deterministic bounded
  sampling with five tightening rules), then evaluates each row with an
  external **coherence score** (0.0 – 1.0) returned by Adaption Labs.

---

## 1. v1 — Profile-calibrated Gaussian Diffusion

### 1.1 What the generator learns

| Column type | Distribution | Implementation |
|---|---|---|
| **8 numerics** (`transaction_amount_usd`, `fee_amount_usd`, `sender_age`, `hour_of_day`, `day_of_week`, `days_since_last_txn`, `account_age_days`, `txn_count_30d`) | Gaussian diffusion (500 timesteps, cosine scheduler, MSE loss), standardised per column | `src/generators/tabddpm_generator.py:142–206` (`train_tabddpm`), on top of `GaussianMultinomialDiffusion` from vendored `lib/tab-ddpm/` |
| **3 categoricals** (`fraud_vector`, `language`, `instrument`) | **Profile-weighted sampling** (NOT multinomial diffusion — multinomial mode-collapse is the reason Tab-DDPM's categorical head was bypassed) | `src/generators/tabddpm_generator.py:209–237` (`sample_categoricals`) |
| **Binary label** (`is_fraud`) | Conditional input to the diffusion model at both train and sample time | `rng.choice([0,1], p=[0.9, 0.1])` — fixed 10 % fraud rate |

### 1.2 Calibration source — the profile configs

`src/scrapers/profile_configs.py` encodes per-archetype priors derived from
**1,040 scraped complaints** (Reddit + CFPB + BBB + niche web):

| Field | Source |
|---|---|
| `language_mix` | Empirical frequency of `detected_language_hints` on scraped records, normalised per archetype. Example for remittance: `{en: 0.78, vi: 0.07, es: 0.06, yo: 0.05, hi: 0.02, ht: 0.02}` (`profile_configs.py:57–65`) |
| `fraud_vectors` | Normalised keyword-counts of `fraud_vector_hint` from the scrape. Remittance uses 11 weighted vectors (wire_transfer 0.21, exchange_rate 0.15, emergency 0.15, …) (`profile_configs.py:67–80`) |
| `instruments` | Curated per archetype (uniform over list). Remittance: Western Union, MoneyGram, Remitly, Xoom, Wire, Hawala, Cash-pickup (`profile_configs.py:82–86`) |
| `transaction_patterns` | `{amount_range: [min, max], median: x, multiplier_when_fraud: [1.2, 3.0]}` — lognormal around median, clamped to range (`profile_configs.py:88–101`) |
| `temporal` | `{peak_hours: [17–22], peak_days: ['Fri','Sat'], weekday_weight, weekend_weight}` (`profile_configs.py:102–105`) |

`build_seed_data()` (`tabddpm_generator.py:65–116`) uses these priors to
synthesise a **3,000-row seed set** per archetype; Tab-DDPM is then trained on
that seed. Synthetic rows sample from the trained diffusion model for
numerics and directly from the profile weights for categoricals.

### 1.3 The v1 quality metric — aggregate summary, no divergence tests

Every archetype emits
`datasets/{archetype}/synthetic/generation_summary.json` with:

```json
{
  "archetype": "remittance",
  "total_synthetic_records": 500,
  "fraud_rate": 0.096,
  "seed_size": 3000,
  "epochs_trained": 700,
  "numerical_columns": [...],
  "amount_stats": {"mean": ..., "median": ..., "min": ..., "max": ...},
  "fraud_vector_distribution": {"wire_transfer": 102, ...},
  "language_distribution": {"en": 389, "es": 31, ...},
  "instrument_distribution": {...}
}
```

**What is NOT computed in v1**:

- No per-column synthetic-vs-seed comparison.
- No statistical distance (KL, Wasserstein, chi-square).
- No marginal test; the implicit assumption is "profile ⇒ seed ⇒ diffusion
  output preserves marginals by construction."
- Only narrative-language match is explicitly validated, via
  `src/generators/verify_language.py` — compares `expected_lang` (from the
  generated record) against `langdetect.detect()` of the Adaption-fill
  narrative. Reports per-language match rate, no CDF comparison.

---

## 2. v2 — Persona-conditioned bounded sampling

### 2.1 Per-persona allocation

`src/generators/tabddpm_v2_generator.py:523–527`:

```python
base = samples_per_archetype // len(personas)   # 5000 / 11 = 454
remainder = samples_per_archetype - base * len(personas)  # 6
allocations = [base] * len(personas)
for i in range(remainder):
    allocations[i] += 1  # first 6 personas get 455 rows, rest 454
```

So 5,000 rows are distributed across 11/11/9/9 personas for
remittance/gig_worker/unbanked/itin respectively. Each persona's block is
sampled independently, then concatenated and shuffled.

### 2.2 Conditioning schema → sampling parameters

`extract_params()` (`tabddpm_v2_generator.py:85–297`) walks the 5 JSON
blocks produced by Adaption's *Expand the World* and builds a flat parameter
dict of 13 keys:

| Generator key | Source in conditioning schema | Role |
|---|---|---|
| `amount_bands` | `transaction_calendar.recurring_windows[].amount_usd` or `.amount_range` | lognormal amount bounds (per platform for gig) |
| `channels` | `transaction_calendar.recurring_windows[].channel` / `transaction_types[].type` | categorical instrument list |
| `hour_ranges` | `recurring_windows[].time_slot_est` / `shift_profile.weekday_peak_hours` | tight windows for `hour_of_day` |
| `peak_days` | `recurring_windows[].day_of_week` | day-of-week weights (peak = 0.4, rest = 0.02) |
| `sub_cadences` | `remittance_cadence.pattern` parsed (weekly 5–9d @0.65, monthly 25–35d @0.35, etc.) | multi-modal `days_since_last_txn` |
| `cadence_days` | derived from `remittance_cadence.frequency_per_day` or `.transaction_chunk_usd` | fallback single cadence |
| `quarterly` | `income_seasonality.quarterly_modifiers` | Q1–Q4 amount multipliers (e.g. `{Q1:1.1, Q2:0.9, Q3:1.0, Q4:1.2}`) |
| `device_type` | `device_fingerprint_evolution.hardware_profile.device_type` | metadata column |
| `device_stability` | `.stability_score` | churn proxy [0.0, 1.0] |
| `age` | persona's `age` | Gaussian jitter around base |
| `languages` | persona's `language_mix` | uniform choice |
| `loss_tolerance_usd` | persona's `loss_tolerance_usd` | legit-amount ceiling |
| `platform_schedules` | built from `remittance_cadence.method + platform_distribution + active_windows` (gig only) | `{platform: {hours, weight, amount, cadence, fee}}` — enables joint sampling |

### 2.3 Sampling paths inside `sample_persona()`

There are **two paths** depending on whether `platform_schedules` exists.

#### Joint path — gig workers

`tabddpm_v2_generator.py:346–381`. Per row:

1. Pick platform weighted by `persona.platform_distribution`
2. Draw `hour_of_day` from **that platform's** `time_range` (e.g. Amazon Flex
   05-09, Uber Eats 18-23)
3. Draw `transaction_amount_usd` from that platform's `amount_band`
4. Draw `days_since_last_txn` from that platform's cadence

The joint coupling is what eliminated "Amazon Flex at 3 am" rows at R4.

#### Independent path — remittance, unbanked, itin

`tabddpm_v2_generator.py:410–497`. Columns sampled independently:

- `transaction_amount_usd`: lognormal on `amount_bands`, capped at
  `loss_tolerance_usd * 1.1` for legit, multiplied by ` U(1.5, 3.5)` for fraud
- `hour_of_day`: uniform over concatenated `hour_ranges`, Gaussian jitter σ=0.5
- `day_of_week`: weighted categorical with `peak_days` dominant
- `days_since_last_txn`: weighted choice across `sub_cadences`
- `fee_amount_usd`: persona's `fee_per_transaction_usd` ± 10 % if fixed, else
  2–5 % of amount
- `account_age_days`: `Normal(sender_tenure_years * 365, 0.15 * mean)`
- `txn_count_30d`: `Poisson(30 / avg_cadence_days)` clamped to `[1, 3×]`

### 2.4 The five tightening rules (ARCHITECTURE.md §4b + source)

| # | Rule | Expression | Effect |
|---|---|---|---|
| 1 | Loss-tolerance cap | `amount_legit ≤ loss_tolerance_usd * 1.1` | stops $500 legit txns on a $100-tolerance persona |
| 2 | Tight hour jitter | σ = 0.3 (joint) / 0.5 (independent); fraud offset ±3–4 h | no 3 am rows for 9-5 personas |
| 3 | Realistic fees | use persona's stated `fee_per_transaction_usd` (e.g., $1.99 DoorDash) | no more fee-as-percent coherence violations |
| 4 | Cadence-derived txn_count_30d | `Poisson(30 / avg_cadence_days)` | biweekly ⇒ ~2/month, not 25 |
| 5 | Tenure-derived account_age | `N(tenure_years × 365, 0.15)` | 22-yr sender ⇒ ~8000 day account, not random |

### 2.5 The v2 distribution metric — coherence score

The headline change: v2 scores **each synthetic row against its source
persona** using Adaption Labs' coherence recipe, returning a structured
verdict.

**Scoring prompt** (`src/personas/persona_verify.py:71–76`):

```python
"Score the behavioral coherence (0.0-1.0) of this transaction against the persona. "
'Return JSON {"coherence_score": float, "violations": [str], "rationale": str}. '
f"Persona:\n{json.dumps(persona)}\n\nTransaction:\n{json.dumps(txn_dict)}"
```

Adaption is run with `reasoning_traces: True` and
`prompt_metadata_injection: True` so the scorer enumerates constraint
violations before producing the final score.

**Threshold & aggregation** (`src/personas/parse_outputs.py:36, 111-112`):

```python
COHERENCE_FLAG_THRESHOLD = 0.6
flagged = df[df["coherence_score"] < 0.6]
flagged.to_parquet(base / "flagged_for_regen.parquet", index=False)
```

Per-archetype stats in `datasets_v2/coherence_summary.json`:

```json
{
  "remittance": {
    "n_rows": 50, "parsed_ok": 50, "with_score": 50,
    "mean_coherence": 0.516,
    "flagged_for_regen": 28, "flag_rate": 0.56
  },
  ...
}
```

Three observables emerge from the coherence scoring:

| Metric | Definition | Round-level signal |
|---|---|---|
| `mean_coherence` | Arithmetic mean of scores | aggregate quality |
| `flag_rate` | Share of rows `< 0.6` | weak-row prevalence |
| `≥0.8 pass rate` (derived) | Share of rows `≥ 0.8` | "production-grade" share |

Round progression (n = 50/archetype except R1 = 200):

| Round | Mean | ≥0.6 pass | ≥0.8 pass | Flag rate |
|---|---:|---:|---:|---:|
| R1 (baseline, random persona) | 0.125 | 1 % | ~0 % | 99 % |
| R2 (persona-anchored)         | 0.515 | 41 % | 15 % | 59 % |
| R3 (cadence/fee tightened)    | 0.562 | 51 % | 32 % | 49 % |
| R4 (joint platform+hour)      | 0.581 | 54 % | 34 % | 46 % |

### 2.6 Violations — per-column catch without divergence tests

Each flagged row carries a `violations` array from the Adaption scorer. This
is the closest thing v1/v2 have to a per-column distribution test — but it is
**qualitative not statistical**:

```
["Temporal frequency deviation: 14-day inter-transaction interval contradicts
  established weekly transaction cadence.",
 "Fee ratio inconsistency: 4.2% fee violates persona's stated $1.99 flat fee."]
```

Reading violations per round drove each tightening rule (see §2.4).

---

## 3. Cross-cutting gaps

| Gap | v1 | v2 |
|---|---|---|
| Synthetic-vs-seed marginal comparison (per column) | ❌ | ❌ |
| Statistical divergence test (KL, Wasserstein, chi-sq) | ❌ | ❌ |
| Per-column flagging | ❌ | Indirect — coherence violations are text not structured |
| Time-series / cadence CDF test | ❌ | ❌ |
| Device distribution validation | ❌ | ❌ |
| Language validation (narrative) | ✅ `verify_language.py` | ✅ same script |
| Behavioural coherence scoring | ❌ | ✅ Adaption API |
| Per-row regen candidate list | ❌ | ✅ `flagged_for_regen.parquet` |

---

## 4. Suggested future metrics

If distribution integrity becomes load-bearing for downstream models, the
obvious additions are:

1. **Per-column Wasserstein(synthetic, profile-expected)** for each numeric
   — flag columns where distance > threshold.
2. **Chi-square test** on categorical distributions (fraud_vector, language,
   instrument) against profile weights, reported in `generation_summary.json`.
3. **Per-persona joint-coupling audit** — for gig workers, verify
   Amazon-Flex rows really are bounded at 05-09, not just on average.
4. **Cadence Kolmogorov-Smirnov test** — compare the empirical CDF of
   `days_since_last_txn` per persona against the declared sub-cadence mixture.
5. **Structured violation taxonomy** — one-hot the free-text `violations`
   list (amount / cadence / fee / platform / fraud-vector) so per-round
   analysis can be automated rather than read by eye.

None of these are blockers today — the coherence score has been a
sufficient integrative metric to drive four rounds of generator tightening —
but they would replace the "read violations, tighten one knob, re-run"
loop with a more automated pipeline.

---

## 5. File map

```
src/scrapers/profile_configs.py                    v1 archetype priors
src/generators/tabddpm_generator.py                v1 generator + summary
src/generators/verify_language.py                  narrative-language QA
src/personas/expand_world.py                       v2 stage 2 (world expansion)
src/personas/parse_outputs.py                      v2 stages 3 + 6 (parse JSON → parquet, flag threshold)
src/generators/tabddpm_v2_generator.py             v2 persona-conditioned sampler
src/personas/persona_verify.py                     v2 coherence scoring
datasets/{archetype}/synthetic/generation_summary.json          v1 aggregate report
datasets_v2/{archetype}/synthetic/generation_summary.json       v2 aggregate report
datasets_v2/{archetype}/persona_verification/coherence_report.parquet    all scored rows
datasets_v2/{archetype}/persona_verification/flagged_for_regen.parquet   scores < 0.6
datasets_v2/coherence_summary.json                 aggregate per archetype
datasets_v2/exports/coherence_progression.csv      4-round mean + pass-rate history
```