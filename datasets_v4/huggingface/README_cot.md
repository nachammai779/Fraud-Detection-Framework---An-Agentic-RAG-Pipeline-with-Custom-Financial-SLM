---
license: cc-by-4.0
task_categories:
  - text-generation
  - text-classification
language:
  - en
  - es
  - vi
  - wo
  - yo
  - hi
  - fr
  - ko
  - zh
  - ru
  - tw
  - am
  - ar
  - ta
  - ja
  - te
  - fil
  - mr
  - ceb
  - gu
tags:
  - fraud-detection
  - chain-of-thought
  - reasoning-traces
  - synthetic-data
  - sft
  - llm-as-judge
  - persona-conditioned
  - citation-grounded
  - fincen-typology
pretty_name: Persona-Conditioned Fraud Detection — CoT Reasoning Companion (v4)
size_categories:
  - 1K<n<10K
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/train.parquet
---

# Persona-Conditioned Fraud Detection — CoT Reasoning Companion (v4)

A 3,926-row chain-of-thought dataset for SFT and LLM-as-judge work. Each
row pairs a v4 fraud-narrative transaction with a step-by-step reasoning
trace explaining how an analyst would evaluate it.

This is the **companion repo** to
[`Nachammai41/underserved-persona_conditioned-fraud-v4`](https://huggingface.co/datasets/Nachammai41/underserved-persona_conditioned-fraud-v4)
(20,300-row narrative dataset + persona/source/typology references). The
two are split by size: keep the main repo lean, the CoT traces here.

## Headline

| | |
|---|---|
| Rows | **3,926** |
| Class balance | 1,963 fraud / 1,963 matched non-fraud (1:1 by archetype, instrument, amount band) |
| Adaption quality | E (5.0) → **A (9.6)**, +92% |
| Trace fill rate | 100% |
| Languages | 20 (same as parent dataset) |

## Quick start

```python
from datasets import load_dataset

cot = load_dataset(
    "Nachammai41/underserved-persona_conditioned-fraud-v4-cot",
    split="train",
)

print(cot[0]["cot_reasoning_trace"])    # step-by-step reasoning
print(cot[0]["cot_completion"])         # final verdict + supporting analysis
print(cot[0]["narrative_text"])         # the v4 narrative under review
print(cot[0]["is_fraud"])               # ground-truth label
```

To enrich a row with full v4 context (persona profile, source citations,
typology definitions), load the parent dataset and join on `data_uuid`:

```python
parent = load_dataset(
    "Nachammai41/underserved-persona_conditioned-fraud-v4",
    name="all", split="train",
).to_pandas().set_index("data_uuid")

cot_df = cot.to_pandas()
enriched = cot_df.merge(parent, left_on="data_uuid", right_index=True,
                        how="left", suffixes=("", "_parent"))
```

## Schema

| Column | Type | Notes |
|---|---|---|
| All 28 transaction columns from parent | — | inherited from the v4 row this trace is about |
| `amount_band` | category | xs / s / m / l / xl — used for fraud↔non-fraud matching |
| `cot_completion` | string | Final analyst verdict + supporting analysis |
| `cot_reasoning_trace` | string | Step-by-step reasoning |
| `enhanced_prompt` | string | Adaption's rephrased prompt (audit trail) |

Reasoning traces average ~6 KB per row.

## How the pairs were selected

For each of the **1,963 fraud rows** in the parent v4 dataset:

1. Find non-fraud candidates in the same `archetype` and same
   `instrument`, within the same log-spaced `amount_band`.
2. If no strict triple match, relax to (archetype, amount_band).
3. Pick one without replacement; record the pairing.

887 of 1,963 fraud rows fell back to the relaxed (archetype, amount_band)
match — still 2 of 3 dimensions matched. The result is a roughly balanced
"hard negatives" set: each fraud row sits next to a non-fraud row that
looks similar on the structured features.

## Suggested uses

- **SFT for fraud-analyst LLMs** — train a model to emit reasoning traces
  given (transaction metadata + narrative) → verdict.
- **LLM-as-judge fine-tuning** — distill the reasoning style into a smaller
  model used in evaluation pipelines.
- **CoT data augmentation** — combine with the parent's 20,300-row bundle
  for mixed reasoning + narrative-only training.
- **Hard-negatives evaluation set** — the 1:1 matched pairs make a clean
  test bed for measuring how well a fraud detector handles look-alike
  legitimate transactions.

## License

CC-BY-4.0. Same provenance and disclaimers as the parent dataset:
synthetic transactions about fictional personas, narratives and reasoning
traces are LLM-generated, no real persons or real fraud cases involved.

## Credits

- **Adaption Labs** — `reasoning_traces` recipe (the source of these traces)
- Parent dataset (citation-grounded personas + typology + sources):
  [`Nachammai41/underserved-persona_conditioned-fraud-v4`](https://huggingface.co/datasets/Nachammai41/underserved-persona_conditioned-fraud-v4)
- Underlying source registry, FinCEN typology, and persona grounding
  documented in the parent repo's README.