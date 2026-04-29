# datasets_v4/v4_1

Patch layer that brings the v4 dataset from 18/25 to **25/25** FinCEN
typology coverage and cleans residual narrative issues. v4.1 does not
regenerate the v4 baseline — it edits in place and adds 300 new rows.

## Headline numbers

| Metric | Before v4.1 | After v4.1 |
|---|---:|---:|
| Rows | 20,000 | **20,300** |
| Typology codes covered | 18 / 25 | **25 / 25** |
| Prompt-tag leakage | 1,235 rows | **0** |
| Empty narratives | 47 | 39 |
| Persona fraud-exposure entries | 24 | 27 |
| Adaption credits spent | — | **~4** |

## What's in this directory

```
v4_1/
├── README.md                              this file
├── ARCHITECTURE.md                        full v4.1 walkthrough
├── empties_reprompt.jsonl                 52 prompts pulled from the original 20k upload
├── empties_manifest.csv                   uuid → archetype manifest for the empties
├── missing_typology_for_adaption.jsonl    300 prompts (100 each for T7 / T8 / HUMAN_TRAFFICKING)
├── missing_typology_rows.parquet          the 300 synthesised rows (narratives filled post-download)
├── combined_upload.jsonl                  merged 352-row JSONL submitted to Adaption (gitignored)
├── adapted_output.jsonl                   raw Adaption output (gitignored)
└── run_metadata.json                      dataset_id, run_id, status, fill counts
```

## What v4.1 changed

1. **Stripped prompt-tag leakage** from 1,235 narratives (~5.8% of v4 rows).
   Adaption was echoing the upload metadata block (persona_id + data_uuid +
   is_fraud + language) into the completion body. Anchor on `data_uuid` and
   trim from there backward.
2. **Re-stamped 4 shadowed FTA codes** (T4, T6, T9, T11) on a half-cap subset
   so both the FTA and SAR equivalents carry rows. No Adaption credits.
3. **Added 3 missing typology codes** (T7 Abuse of Access, T8 Refusal to
   Cooperate, SAR_HUMAN_TRAFFICKING) by patching one persona each
   (`unb_001`, `gig_001`, `itin_010`) with a documented fraud-exposure
   event, then synthesising 100 transactions per code (300 total) and
   filling narratives via Adaption.
4. **Refilled 51 of 52 empty narratives** by resubmitting the original
   prompts. (1 came back empty again; 12 returned an empty string.)

## Reproducing

```bash
python src/personas_v4/strip_prompt_leakage.py
python src/personas_v4/v4_1_restamp_shadowed.py
python src/personas_v4/v4_1_add_missing_typologies.py
python src/personas_v4/build_v4_1_reprompt.py

ADAPTION_API_KEY=... python src/personas_v4/v4_1_adaption_job.py --submit
ADAPTION_API_KEY=... python src/personas_v4/v4_1_adaption_job.py --check
ADAPTION_API_KEY=... python src/personas_v4/v4_1_adaption_job.py --download
```

The `--download` step runs the merge automatically, prints final coverage,
and rebuilds `datasets_v4/exports/transactions_v4_20k.{parquet,csv}`.

## Where to read more

- Patch-layer architecture details: `ARCHITECTURE.md` (this directory)
- v4 baseline: `../ARCHITECTURE.md`
- Distribution + coverage tables: `../DISTRIBUTION_METRICS.md`
- Top-level overview: `../README.md`

## Note on distribution metrics

v4.1 does **not** change the sampling mechanics or persona conditioning of
v4. The only distribution-level effects are:

- Typology coverage table grows by 7 codes (4 via re-stamp, 3 via persona
  events). Documented in `../DISTRIBUTION_METRICS.md` §2.
- 300 rows added; per-archetype counts shift from 5,000 each to:
  remittance=5,000, gig_worker=5,100, unbanked=5,100, itin=5,100.
- Three personas gain a new `family_crisis_history` event and a fraud-
  exposure grounding entry — no grade changes.

No standalone `DISTRIBUTION_METRICS.md` for v4.1; the parent v4 doc covers
the unified post-v4.1 state.