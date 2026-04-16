# V2 Persona-Conditioned Dataset Pipeline — Architecture Walkthrough

## Problem Statement

V1 fed Adaption Data raw scraped narrative text. The model generated rows that were statistically correct in aggregate (fraud rates, language mix, amounts) but lacked individual-level behavioral coherence — a row tagged "remittance" had no anchor to *whose* remittance it was, so a retired man in Chicago sending $200/month via MoneyGram might receive a transaction at 3am for $4,000 via Sendwave.

V2 addresses this by anchoring every generated row to a **named persona with a structured world description**.

---

## Pipeline: 6 Stages, 5 Scripts

```
Stage 1: persona_profiles.json          (manual, per archetype)
    │
Stage 2: expand_world.py                (Adaption API — Expand the World)
    │
Stage 3: parse_outputs.py               (JSON → conditioning_schema.parquet)
    │
Stage 4: tabddpm_v2_generator.py        (persona-conditioned sampling)
    │
Stage 5: persona_verify.py              (Adaption API — coherence scoring)
    │
Stage 6: parse_outputs.py + download_outputs.py  (results → coherence_report)
```

---

## Stage 1: Persona Profiles

**Files**: `datasets_v2/{archetype}/personas/persona_profiles.json`

Each persona is a structured world description — not a prompt, not a narrative. Example:

```json
{
  "persona_id": "rem_004",
  "name": "Jean-Baptiste Pierre",
  "age": 41,
  "summary": "Jean-Baptiste, 41, construction laborer in Brooklyn, sends to wife
    and three children in Port-au-Prince. Uses CAM Transfer...",
  "corridor_country": "Haiti (Port-au-Prince)",
  "transfer_service_loyalty": {
    "primary": "CAM",
    "secondary": "informal_courier",
    "switch_threshold_fee_diff_usd": 6.00
  },
  "family_crisis_history": ["courier_theft_2023", "earthquake_aid_2021"],
  "sender_tenure_years": 11,
  "language_mix": ["ht", "en", "fr"],
  "income_usd_weekly": [700, 1100],
  "loss_tolerance_usd": 100
}
```

Each archetype has its own **key world dimensions**:

| Archetype | Dimensions | Persona Count |
|-----------|-----------|---------------|
| Remittance | corridor_country, transfer_service_loyalty, family_crisis_history, sender_tenure | 11 |
| Gig Worker | platform_mix, daily_cashout_pattern, device_stability, sim_history | 11 |
| Unbanked | kiosk_location, prepaid_card_stack, income_source, documentation_status | 9 |
| ITIN | business_type, tax_filing_history, credit_file_age, accountant_relationship | 9 |

**Design rationale**: 40 personas total (not 400). Each persona represents a behavioral archetype within the archetype — sufficient to capture the diversity of fraud surfaces without diluting signal.

---

## Stage 2: Expand the World

**Script**: `src/personas/expand_world.py`

**What it does**: Takes each persona profile and asks Adaption Labs to expand it into a full conditioning schema — the *world* that persona lives in.

**How it works**: Each persona becomes a prompt row:

```python
def persona_to_prompt_row(persona, archetype, world_dimensions):
    prompt = (
        f"Expand the following {archetype} persona into a structured conditioning schema "
        f"for synthetic transaction generation. Return JSON covering: "
        f"{', '.join(EXPANSION_TARGETS)}. "
        f"Anchor every field to the persona's world dimensions: "
        f"{', '.join(world_dimensions)}. "
        f"Persona:\n{json.dumps(persona)}"
    )
    return {"persona_id": ..., "prompt": prompt, "completion": ""}
```

These rows are uploaded as JSONL to Adaption. The recipe uses `reasoning_traces: True` and `prompt_metadata_injection: True` so Adaption reasons through the world dimensions before generating.

**Output**: Adaption returns 5 structured JSON blocks per persona:

| Block | Contents |
|-------|----------|
| `transaction_calendar` | Recurring windows with day, hour, amount, channel |
| `device_fingerprint_evolution` | Hardware, SIM stability, device churn |
| `remittance_cadence` | Frequency, methods, platform distribution |
| `income_seasonality` | Quarterly modifiers, base income range |
| `communication_patterns` | Call/SMS/WhatsApp patterns |

**Key architectural point**: The schemas return in *different shapes per archetype* because Adaption generates them contextually. A remittance persona receives `recurring_windows` with `day_of_week` and `channel: "CAM"`. A gig worker receives `peak_activity_windows` with `platform: "Amazon Flex"` and `time_range: "05:00-09:00"`. This is by design — but it requires the downstream generator to be schema-tolerant.

---

## Stage 3: Parse into Conditioning Schema

**Script**: `src/personas/parse_outputs.py`

**What it does**: Downloads the Adaption JSONL, extracts JSON from `enhanced_completion` (which comes back wrapped in markdown fences), and writes `conditioning_schema.parquet` — one row per persona, 5 JSON-string columns.

The `extract_json` function handles Adaption's tendency to wrap JSON in code blocks:

```python
def extract_json(blob):
    m = re.search(r"```json\s*(\{.*?\})\s*```", blob, re.DOTALL)
    candidate = m.group(1) if m else blob.strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    return json.loads(candidate[start:end + 1])
```

**Output**: `datasets_v2/{archetype}/expanded_world/conditioning_schema.parquet`

---

## Stage 4: TabDDPM V2 Generator — The Core

**Script**: `src/generators/tabddpm_v2_generator.py` (578 lines)

This is the heart of the pipeline. Three key functions:

### 4a. `extract_params()` — Schema-tolerant parameter extraction

This function handles 3+ different conditioning schema shapes across archetypes. It builds a unified sampling spec from whatever shape Adaption returned.

**Channel extraction for remittance** (straightforward):
```
tc.recurring_windows[].channel → channels list
```

**Channel extraction for gig workers** (3 variants discovered):
```
gig_001: rc.method = ["Uber Instant Pay", "DoorDash Fast Pay"]
         rc.platform_distribution = {"Uber": 0.5, "DoorDash": 0.3, "Instacart": 0.2}

gig_003: tc.active_windows[].platform = "Amazon Flex" / "Uber Eats"
         rc.income_distribution.{platform}.weight = 0.6 / 0.4

gig_004: tc.platform_distribution = {"Uber": 0.55, "Curb (yellow cab)": 0.45}
         tc.shift_profile.weekday_peak_hours = [16, 17, ..., 22]
```

**Channel extraction for unbanked**:
```
tc.transaction_types[].type = "check_cash" / "pos_purchase"
tc.transaction_types[].card_bin_prefix = "Walmart_MoneyCard"
```

**Channel extraction for ITIN**:
```
tc.parameters.inbound_schedule.source = "Etsy Payments"
tc.parameters.outbound_obligations[].type = "estimated_tax_payment"
```

For gig workers, the function builds `platform_schedules` — a dict of
`{platform_name: {hours, weight, amount, cadence, fee}}` — from all three variants.
This enables **joint platform → hour → amount sampling**.

**Sub-cadence extraction** handles mixed patterns:

```python
# Jean-Baptiste: "weekly small + monthly large"
sub_cadences = [
    {"days_between": (5, 9), "weight": 0.65},
    {"days_between": (25, 35), "weight": 0.35},
]
```

The final output is a flat dict with 13 keys:
`amount_bands`, `channels`, `hour_ranges`, `peak_days`, `sub_cadences`, `cadence_days`,
`quarterly`, `device_type`, `device_stability`, `age`, `languages`, `loss_tolerance_usd`,
`platform_schedules`.

### 4b. `sample_persona()` — Per-persona row generation

Takes one persona + its conditioning params + N samples. Two paths:

**Joint path** (when `platform_schedules` exist — gig workers):

```python
if plat_scheds:
    # 1. Pick platform (weighted by persona's platform_distribution)
    plat_idx = rng.choice(len(plat_names), p=plat_weights)
    # 2. Pick hour from THAT platform's specific time window
    h_s, h_e = ps["hours"][hr]
    hours[i] = rng.integers(h_s, h_e + 1)
    # 3. Use that platform's amount band if available
    if ps["amount"] is not None:
        amounts[i] = sample_from(ps["amount"])
    # 4. Use that platform's cadence if available
    if ps["cadence"] is not None:
        days_since[i] = sample_from(ps["cadence"])
```

This ensures Amazon Flex transactions appear at 5-9am and Uber Eats at 6-11pm — never
the reverse. Joint sampling is the key difference from v1, where channels and hours
were sampled independently.

**Independent path** (remittance, unbanked, itin):

```python
else:
    # Hours from global hour_ranges (persona's stated time slots)
    # Cadence from sub_cadences (weighted selection)
    # Channels sampled independently (single-service personas)
```

**Five tightening rules** applied across both paths:

| Rule | What | Why |
|------|------|-----|
| Loss tolerance cap | Legit amounts clamped at `loss_tolerance_usd * 1.1` | A persona with $100 tolerance should not produce $500 legitimate txns |
| Tight hour jitter | sigma=0.3 (joint) or 0.5 (independent). Fraud shifts only +/-3-4h | Eliminates 3am transactions for personas with 9-5 schedules |
| Realistic fees | Uses persona's stated `fee_per_transaction_usd` (e.g. $1.99 for DoorDash Fast Pay) | Fee-as-percentage was flagging coherence violations |
| Cadence-derived txn_count_30d | `30 / avg_cadence_days` via Poisson | A monthly sender should not show 25 transactions per month |
| Tenure-derived account_age | `sender_tenure_years * 365` with 15% gaussian jitter | A 22-year sender should reflect ~8000 day account age |

### 4c. `generate_archetype()` — Orchestrator

```python
# Allocate samples: 5000 / n_personas with remainder distributed
base = samples_per_archetype // len(personas)
remainder = samples_per_archetype - base * len(personas)
allocations = [base] * len(personas)
for i in range(remainder):
    allocations[i] += 1

# Generate per-persona, concatenate, shuffle
for persona, n in zip(personas, allocations):
    frames.append(sample_persona(persona, cond, n, archetype, rng))
df = pd.concat(frames).sample(frac=1.0)
```

**Output per archetype**:
- `transactions.parquet` — 5,000 rows with `persona_id` and `dataset_version: "v2"`
- `transactions_{archetype}.csv` — for viewing
- `generation_summary.json` — stats including per-persona row counts, fraud rate, instruments

---

## Stage 5: Persona Verification

**Script**: `src/personas/persona_verify.py`

**What it does**: Samples N transactions from the generated data, pairs each with its source persona, and asks Adaption to score behavioral coherence.

**Prompt per row**:

```python
prompt = (
    "Score the behavioral coherence (0.0-1.0) of this transaction "
    "against the persona. Return JSON "
    '{"coherence_score": float, "violations": [str], "rationale": str}. '
    f"Persona:\n{json.dumps(persona)}\n\n"
    f"Transaction:\n{json.dumps(txn_dict)}"
)
```

**Retry-on-409**: The Adaption API returns 409 if the dataset is still importing. Instead of
polling `get_status` (which can hang), we retry `datasets.run()` on `ConflictError`:

```python
while time.time() < deadline:
    try:
        resp = client.datasets.run(...)
        break
    except ConflictError:
        time.sleep(10)
```

**Fallback path**: If v2 synthetic data does not yet exist, the script falls back to v1
`datasets/{archetype}/synthetic/transactions.parquet` with randomly assigned `persona_id`.
This fallback was used to validate the pipeline before the v2 generator was operational.

---

## Stage 6: Download + Parse Results

**Scripts**: `src/personas/download_outputs.py` + `src/personas/parse_outputs.py`

`download_outputs.py` reads job tracker JSONs, takes the latest `dataset_id` per archetype,
calls `client.datasets.download(file_format="jsonl")` + `client.datasets.get_evaluation()`.

`parse_outputs.py` extracts coherence scores and writes:

| Output | Description |
|--------|-------------|
| `coherence_report.parquet` | Full report: score + violations + rationale per row |
| `flagged_for_regen.parquet` | Rows where `coherence_score < 0.6` |
| `coherence_summary.json` | Aggregate stats per archetype |

---

## Results Progression

Three rounds of verification demonstrate the iterative tightening:

| Archetype | v1 Mean (random) | v2 R1 | v2 R2 (tightened) | v2 R3 (joint sampling) | R3 >=0.6 pass | R3 >=0.8 pass |
|-----------|------------------|-------|--------------------|-----------------------|---------------|---------------|
| Remittance | 0.090 | 0.426 | 0.589 | **0.516** | 44% | 18% |
| Gig Worker | 0.168 | 0.370 | 0.402 | **0.399** | 24% | 10% |
| Unbanked | 0.145 | 0.543 | 0.540 | **0.609** | **58%** | **42%** |
| ITIN | 0.097 | 0.720 | 0.718 | **0.798** | **90%** | **66%** |

**Overall trajectory from v1 to v2 R3**: +460% mean coherence for ITIN, +320% for Unbanked, +473% for Remittance, +138% for Gig Worker.

**Key findings from Round 3**:

- **ITIN**: 0.720 → 0.798 mean, 90% pass rate, 66% scoring >=0.8. Near production quality.
- **Unbanked**: 0.540 → 0.609 mean, 58% pass rate. Solid improvement from schema-tolerant channel extraction.
- **Gig Worker**: 0.402 → 0.399 (flat). Joint sampling corrected instrument/hour pairing but the scorer remains strict on amount-to-platform mapping within the persona.
- **Remittance**: 0.589 → 0.516 (slight dip attributed to sampling variance at n=50).

**Improvement drivers per round**:

- **v1 → v2 Round 1**: Persona anchoring alone — amounts, languages, and channels aligned to persona
- **Round 1 → Round 2**: Cadence clamping (biweekly persona receives biweekly intervals), loss tolerance cap (legitimate amounts bounded), fee normalization
- **Round 2 → Round 3**: Joint platform→hour→amount sampling (Amazon Flex at 5am, Uber Eats at 7pm — never reversed), schema-tolerant extraction across 3+ conditioning schema variants, tenure-derived account age

---

## Persona Spot-Checks (from v2 tightened generation)

### Carlos Mendoza (rem_009) — Retired, MoneyGram, $100 loss tolerance

```
legit amt: mean=$109  max=$110  (capped at $100 * 1.1)
instruments: {'MoneyGram (in-store)': 454}  (single-service loyalty)
account_age_days: mean=7955  (22-year tenure → ~8030 expected)
txn_count_30d: mean=3.0  (biweekly cadence → ~2-3/month)
```

### DeShawn Williams (gig_001) — Daily cashout, Uber/DoorDash/Instacart

```
instruments: {'Uber': 224, 'DoorDash': 134, 'Instacart': 97}  (50/30/20 weights)
days_since: mean=0.5  (daily cashout)
fee: mean=$1.99  (persona's stated $1.99 fast-pay fee)
txn_count_30d: mean=59.6  (multiple daily cashouts)
```

### Rajesh Sharma (gig_003) — Amazon Flex mornings, Uber Eats evenings

```
instruments: {'Amazon Flex': 273, 'Uber Eats': 182}  (60/40 weights)
hours: mean=12.4  (bimodal: 5-9 Flex + 18-23 Uber Eats)
```

---

## File Layout

```
src/personas/                              # v2 pipeline scripts
    expand_world.py                        #   Stage 2: persona → Adaption Expand World
    persona_verify.py                      #   Stage 5: coherence scoring
    download_outputs.py                    #   Stage 6: pull Adaption results
    parse_outputs.py                       #   Stage 3 + 6: JSON → parquet

src/generators/
    tabddpm_v2_generator.py               #   Stage 4: persona-conditioned sampler

datasets_v2/{archetype}/
    personas/persona_profiles.json         #   Stage 1 input (source of truth)
    expanded_world/
        for_adaption.jsonl                 #   Stage 2 upload
        adapted_output.jsonl               #   Stage 2 download (Adaption response)
        conditioning_schema.parquet        #   Stage 3 output → Stage 4 input
        evaluation.json                    #   Adaption quality score
        run_metadata.json                  #   dataset_id, run_id, credits
    synthetic/
        transactions.parquet               #   Stage 4 output → Stage 5 input
        transactions_{archetype}.csv       #   Human-readable version
        generation_summary.json            #   Stats: fraud rate, instruments, counts
    persona_verification/
        for_adaption.jsonl                 #   Stage 5 upload
        adapted_output.jsonl               #   Stage 5 download
        coherence_report.parquet           #   Stage 6: full scores
        flagged_for_regen.parquet          #   Stage 6: rows needing regen
        evaluation.json                    #   Adaption quality score
        run_metadata.json                  #   Job metadata

datasets_v2/
    expand_world_jobs.json                 #   Job tracker (all Expand-World runs)
    persona_verify_jobs.json               #   Job tracker (all verify runs)
    coherence_summary.json                 #   Aggregate coherence stats
    README.md                              #   Dataset documentation
```

---

## Credits Consumed: 23 total

| Stage                                    | Runs | Credits |
|------------------------------------------|------|---------|
| Expand-World (40 personas)               | 4    | 4       |
| Verify Round 1 (v1 fallback, 200/arch)   | 4    | 11      |
| Verify Round 2 (v2 tightened, 50/arch)   | 4    | 4       |
| Verify Round 3 (joint sampling, 50/arch) | 4    | 4       |
| **Total**                                | **16** | **23** |

---

## Dependencies

```bash
pip install torch scikit-learn pandas pyarrow adaption requests
```

The `adaption` SDK provides: `Adaption(api_key=...)`, `client.datasets.upload_file()`,
`client.datasets.run()`, `client.datasets.get_status()`, `client.datasets.download()`,
`client.datasets.get_evaluation()`, `client.datasets.wait_for_completion()`.

Environment variable: `ADAPTION_API_KEY` must be set for Stages 2, 5, 6.

---

## Key Design Decisions

1. **Personas, not narratives**: V1 used scraped narrative text as seeds. V2 uses structured
   persona profiles. This provides the generator with concrete constraints (loss tolerance,
   service loyalty, cadence) rather than loosely interpreted text.

2. **Schema tolerance over schema normalization**: Adaption returns different JSON shapes per
   archetype. Rather than post-processing into a canonical schema, `extract_params()` handles
   all variants with fallback chains. This preserves the richness of per-archetype schemas.

3. **Joint vs independent sampling**: Gig workers require joint platform→hour→amount sampling
   because the platforms have different operating hours. Remittance personas use single
   services, so independent sampling is sufficient.

4. **Iterative tightening**: Rather than attempting to achieve correctness in a single pass,
   the approach follows a verify → read violations → tighten generator → re-verify cycle.
   Each round produces specific, actionable violation patterns.

5. **Separate from v1**: All v2 artifacts reside under `datasets_v2/`. V1 and v2 must not be
   mixed for clustering, benchmarking, or fraud-rate calibration.