# Dataset v2 — Persona-Conditioned Generation

v2 replaces narrative-text seeding with **structured persona profiles**. Adaptive Data's "Expand the World" turns each persona into a conditioning schema (transaction calendar, device evolution, cadence, seasonality, comms), and Tab-DDPM samples conditional on that schema rather than from priors alone.

## Why v2

v1 fed Adaptive Data scraped narrative text. The model had no anchor for *whose* world it was generating — fraud vectors and language mix were correct in aggregate but rows were not behaviorally coherent at the individual level. v2 anchors every generated row to a named persona with a structured world description.

## Persona Inventory (40 total)

| Archetype | Personas | Key World Dimensions |
|-----------|----------|----------------------|
| Remittance | 11 | corridor_country, transfer_service_loyalty, family_crisis_history, sender_tenure |
| Gig Worker | 11 | platform_mix, daily_cashout_pattern, device_stability, sim_history |
| Unbanked | 9  | kiosk_location, prepaid_card_stack, income_source, documentation_status |
| ITIN | 9  | business_type, tax_filing_history, credit_file_age, accountant_relationship |

All persona files: `datasets_v2/{archetype}/personas/persona_profiles.json`.

## Pipeline (vs v1)

```
v1: scraped narratives -> Adaptive (rewrite) -> TabDDPM (priors only) -> narratives
v2: persona profiles   -> Adaptive (Expand World) -> conditioning schema
                                                          |
                                                          v
                                                    TabDDPM (conditioned)
                                                          |
                                                          v
                                          synthetic txns w/ persona_id
                                                          |
                                                          v
                                Adaptive (persona_coherence_check)  <- 2nd pass verify
```

## Per-archetype directory layout

```
datasets_v2/{archetype}/
  personas/persona_profiles.json        # source of truth for the world
  expanded_world/                       # Adaptive Data Expand-World output
    expanded_world.jsonl
    conditioning_schema.parquet         # input to TabDDPM
  synthetic/
    transactions.parquet                # TabDDPM conditioned output
  adaptive/                             # narrative fill (v2 reuses v1 stages)
  reasoning/                            # CoT traces
  persona_verification/                 # 2nd-pass coherence check
    coherence_report.jsonl
    flagged_for_regen.parquet
```

## Commands

```bash
# Expand each persona into a conditioning world
python src/personas/expand_world.py --all

# Tab-DDPM (conditioned on expanded_world/conditioning_schema.parquet)
# (TabDDPM v2 generator — pass --conditioning_schema; not yet implemented in this commit)

# Verify behavioral coherence of generated records
python src/personas/persona_verify.py --all --sample 500
```

## Cluster separately from v1

v2 records carry `persona_id` and a `dataset_version: "v2"` field. Do not mix with v1 outputs in `datasets/` — clustering, fraud-rate calibration, and benchmark splits should be computed within v2 only.