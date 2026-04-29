# v4.1 — Patch Layer Architecture

> v4.1 is a patch layer on top of v4. It does not regenerate the 20,000-row
> baseline. It cleans residual issues (prompt-tag leakage, empty narratives)
> and closes typology coverage from 18/25 to 25/25. For the v4 baseline
> walkthrough, see the parent `../ARCHITECTURE.md`.

## What v4.1 fixed

| Issue at v4 close | Resolution |
|---|---|
| 1,235 narratives (~5.8%) had Adaption's "Additional Context Tags" block echoed into the completion body (persona_id + data_uuid + is_fraud + language) | `strip_prompt_leakage.py` — anchor on `data_uuid` (a 36-char UUID never appears in real prose), trim from there backward through any preceding separator/persona_id/archetype tokens |
| 4 "shadowed" FTA codes (T4, T6, T9, T11) had 0 rows because the SAR-preference resolver routed their fraud_vectors to SAR equivalents | `v4_1_restamp_shadowed.py` — flip a half-cap subset of rows from SAR to FTA so both codes carry rows; SAR_BEC and SAR_CYBER preserved alongside their FTA twins |
| 3 typology codes (T7 Abuse of Access, T8 Refusal to Cooperate, SAR_HUMAN_TRAFFICKING) had no matching `fraud_vector` in any v4 row | `v4_1_add_missing_typologies.py` — patch 3 personas with a documented fraud event each, synthesise 100 transaction rows per code (300 total), fill narratives via Adaption |
| 47 empty narratives from the original 20k fill | `build_v4_1_reprompt.py` rebuilds the original prompts for those rows; resubmitted in the same Adaption job as the missing-typology fill (51/52 refilled) |

## Pipeline

```
v4 close: 20,000 rows, 18/25 codes, 1,235 leaked narratives, 47 empties
          │
          ▼
strip_prompt_leakage.py  →  20,000 rows, 0 leakage, 52 empties (40 newly visible)
          │
          ▼
v4_1_restamp_shadowed.py  →  18 → 22 codes, no Adaption credits
          │
          ▼
v4_1_add_missing_typologies.py  →  patches 3 personas + writes 300 synth rows
build_v4_1_reprompt.py          →  pulls 52 original prompts for empty rows
          │
          ▼
v4_1_adaption_job.py --submit/--check/--download
  → one Adaption job, 352 rows (300 missing-typology + 52 empties)
  → tagged via `v41_source` so download routes correctly
          │
          ▼
download splits:
  empty_refill rows      → overwrite empty narrative_text in main parquets by data_uuid
  missing_typology rows  → fill narrative_text in v4_1/missing_typology_rows.parquet
                            then append to gig_worker / unbanked / itin parquets
          │
          ▼
v4.1 close: 20,300 rows, 25/25 codes, 39 empties (~0.19%)
```

## Persona patches (3 edits)

Each adds one entry to `family_crisis_history` plus a fraud-exposure
`grounding` block citing FinCEN advisories.

| Persona | Event tag added | Fraud vector | Typology |
|---|---|---|---|
| `unb_001` Dorothy Jackson | `power_of_attorney_abuse_caregiver_2024` | `power_of_attorney_abuse` | FTA_T7 (Abuse of Access) |
| `gig_001` DeShawn Williams | `platform_refusal_records_id_theft_dispute_2024` | `refusal_to_cooperate` | FTA_T8 (Refusal to Cooperate) |
| `itin_010` Fatou Diallo | `wage_confiscation_braider_intermediary_recurring` | `wage_confiscation` | SAR_HUMAN_TRAFFICKING |

Personas are otherwise unchanged. The new grounding entries cite
`fincen_2024_identity_fta` and `fincen_sar_key_terms`.

## Synthetic-row generation (300 rows)

`v4_1_add_missing_typologies.py` does not run TabDDPM again. It samples 100
existing rows from each host persona's slice of `transactions_adapted.parquet`
(with replacement), then overrides:

- `data_uuid` → fresh UUID
- `is_fraud` → 1
- `fraud_vector` → the new vector tag
- `fraud_vector_typology_ref` → the target FTA/SAR code
- `language` → the persona-event language (en, en, wo)
- `narrative_text` → empty (filled by Adaption)
- `dataset_version` → `v4.1`

This keeps amounts, fees, hours, days within the host persona's empirical
distribution while stamping the new fraud signature.

## Re-stamp logic (4 shadowed codes, ~159 rows)

For each (FTA, SAR) pair where both share a fraud_vector:

```python
candidate_rows = rows where (is_fraud=1) and (fraud_vector ∈ vector_list)
                                          and (typology_ref == SAR)
k = min(PER_CODE=100, len(candidates) // 2)   # leave at least half in SAR
sample k rows uniformly, set typology_ref = FTA
```

The half-cap matters: without it, SAR_BEC (88 rows total) and
SAR_CYBER (15 rows total) would have lost all rows when re-stamped to T11
and T9 respectively. With the cap:

| SAR code | Pre-restamp rows | Post (FTA twin gets) | Post (SAR retains) |
|---|---:|---:|---:|
| SAR_BEC_FRAUD | 88 | T11 = 44 | 44 |
| SAR_ATO_FRAUD | 271 | T6 = 100 | 171 |
| SAR_CYBER_EVENTS | 15 | T9 = 7 | 8 |
| SAR_COVID19_IMPOSTER | 25 | T4 = 8 | 17 |

## CoT reasoning dataset (separate artifact)

`datasets_v4/reasoning/cot_dataset.parquet` is built independently of the
v4.1 patch layer:

- `build_cot_job.py` selects all 1,963 fraud rows + 1,963 non-fraud rows
  matched on (archetype, instrument, amount band) → 3,926 rows.
- `cot_adaption_job.py --submit/--check/--download` runs the Adaption
  reasoning_traces recipe.
- Output joined into `cot_dataset.parquet` with `cot_completion` +
  `cot_reasoning_trace` columns appended to the selection.
- Adaption quality grade: E (5.0) → A (9.6), +92%. 100% trace fill.

This dataset feeds SFT/judge training — it is **not** part of the
20,300-row bundle.

## Bundle delta

| | Before v4.1 | After v4.1 |
|---|---:|---:|
| Rows | 20,000 | 20,300 |
| Typology codes | 18 | **25** |
| Empty narratives | 47 (52 after leakage strip) | 39 |
| Prompt-tag leakage | 1,235 rows | **0** |
| Personas with documented fraud-exposure | 24 | 27 (+unb_001, gig_001, itin_010) |

## Credit cost

| Step | Credits |
|---|---:|
| Strip prompt leakage | 0 (post-process script) |
| Re-stamp shadowed codes | 0 (in-place metadata edit) |
| Combined v4.1 Adaption run (300 + 52 = 352 rows) | ~4 |
| **v4.1 total** | **~4** |

## File map

```
datasets_v4/v4_1/
├── README.md                              this directory's overview
├── ARCHITECTURE.md                        this document
├── empties_reprompt.jsonl                 52 prompts pulled from the original 20k upload
├── empties_manifest.csv                   uuid → archetype mapping for the empties
├── missing_typology_for_adaption.jsonl    300 prompts (100 each for T7/T8/HUMAN_TRAFFICKING)
├── missing_typology_rows.parquet          synthesised rows (with filled narratives post-download)
├── combined_upload.jsonl                  merged 352-row JSONL submitted to Adaption (gitignored)
├── adapted_output.jsonl                   raw Adaption output (gitignored)
└── run_metadata.json                      dataset_id, run_id, status, fill counts

src/personas_v4/   (v4.1 patch layer scripts)
├── strip_prompt_leakage.py
├── v4_1_restamp_shadowed.py
├── v4_1_add_missing_typologies.py
├── v4_1_adaption_job.py        (--estimate / --submit / --check / --download wrapper)
├── v4_1_merge_missing.py       (standalone merge step; the wrapper also calls this logic)
└── build_v4_1_reprompt.py
```

## Reproducing v4.1 from scratch

```bash
# 1. Strip prompt-tag leakage (modifies the 4 archetype parquets in place)
python src/personas_v4/strip_prompt_leakage.py

# 2. Restamp shadowed FTA codes (in-place metadata edit, half-cap)
python src/personas_v4/v4_1_restamp_shadowed.py

# 3. Build the missing-typology synth rows + Adaption JSONL
python src/personas_v4/v4_1_add_missing_typologies.py

# 4. Build the empties refill JSONL
python src/personas_v4/build_v4_1_reprompt.py

# 5. Submit the combined Adaption job
ADAPTION_API_KEY=... python src/personas_v4/v4_1_adaption_job.py --submit
ADAPTION_API_KEY=... python src/personas_v4/v4_1_adaption_job.py --check    # poll
ADAPTION_API_KEY=... python src/personas_v4/v4_1_adaption_job.py --download

# --download auto-runs the merge: refills empty narratives by data_uuid,
# appends 300 missing-typology rows to the host parquets, rebuilds the bundle,
# prints final coverage (should read 25 distinct typology codes).
```

## Known limitations

- 39 empty narratives remain — small enough that re-running the empties
  refill on those specific uuids is cheap if needed.
- `wage_confiscation` rows for SAR_HUMAN_TRAFFICKING all share one persona
  (`itin_010`) — diversity is bounded by the patch design choice. Adding
  more personas with this exposure would broaden voice/language coverage.