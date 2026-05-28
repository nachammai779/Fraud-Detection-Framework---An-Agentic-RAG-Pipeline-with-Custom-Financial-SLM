"""Unsloth QLoRA SFT of Gemma 4 E4B-it on the v3 SFT corpus.

Reads:
    data/sft_v3/sft_corpus_train.parquet
    data/sft_v3/sft_corpus_eval.parquet

Writes:
    data/sft_v3/gemma-judge-lora/        (LoRA adapter)
    data/sft_v3/gemma-judge-merged/      (merged FP16 weights, if --save-merged)
    data/sft_v3/gemma-judge-trainer/     (trainer state + checkpoints)

Hardware: any single GPU with >=24GB VRAM (A100 40/80, H100, RTX 4090/3090).

Quickstart:
    pip install unsloth[colab-new] trl peft bitsandbytes accelerate
    python -m src.sft_v3.train_lora

CLI knobs:
    --base-model        HF id of base (default: unsloth's pre-4bit Gemma 4 E4B-it)
    --epochs            number of epochs (default: 2)
    --batch-size        per-device train batch size (default: 2)
    --grad-accum        gradient accumulation steps (default: 8) -> effective bs 16
    --max-seq-length    max packed seq length (default: 4096)
    --lora-r / --lora-alpha   LoRA rank + scaling (default: 16 / 32)
    --learning-rate     default 2e-4
    --save-merged       additionally export FP16 merged weights
    --resume            resume from latest checkpoint in trainer dir
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import pandas as pd
import torch

# Unsloth must be imported BEFORE transformers / peft / trl so the kernel
# monkey-patches take effect.
from unsloth import FastLanguageModel, is_bfloat16_supported  # type: ignore
from unsloth.chat_templates import train_on_responses_only    # type: ignore

from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

TRAIN_PARQUET = Path("data/sft_v3/sft_corpus_train.parquet")
EVAL_PARQUET = Path("data/sft_v3/sft_corpus_eval.parquet")
OUT_LORA = Path("data/sft_v3/gemma-judge-lora")
OUT_MERGED = Path("data/sft_v3/gemma-judge-merged")
OUT_TRAINER = Path("data/sft_v3/gemma-judge-trainer")

DEFAULT_BASE = "google/gemma-4-E4B-it"

# Gemma 4 changed delimiters from <start_of_turn>...<end_of_turn> (Gemma 2/3)
# to <|turn>...<turn|>. train_on_responses_only masks loss on everything before
# the first occurrence of RESPONSE_PART.
INSTRUCTION_PART = "<|turn>user\n"
RESPONSE_PART = "<|turn>model\n"


def _messages_to_text(messages_json: str, tokenizer) -> str:
    msgs = json.loads(messages_json)
    return tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)


def load_datasets(tokenizer) -> tuple[Dataset, Dataset]:
    train_df = pd.read_parquet(TRAIN_PARQUET)
    eval_df = pd.read_parquet(EVAL_PARQUET)
    print(f"[data] train rows: {len(train_df)}")
    print(f"[data] eval  rows: {len(eval_df)}")

    train_df["text"] = train_df["messages"].apply(lambda m: _messages_to_text(m, tokenizer))
    eval_df["text"] = eval_df["messages"].apply(lambda m: _messages_to_text(m, tokenizer))
    # Keep a few metadata columns for later eval breakdowns; SFTTrainer will use "text"
    keep_cols = ["data_uuid", "archetype", "is_fraud", "_source", "text"]
    train_ds = Dataset.from_pandas(train_df[keep_cols], preserve_index=False)
    eval_ds = Dataset.from_pandas(eval_df[keep_cols], preserve_index=False)
    return train_ds, eval_ds


def build_model(args: argparse.Namespace):
    print(f"[model] loading base: {args.base_model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )

    print(f"[model] attaching LoRA r={args.lora_r} alpha={args.lora_alpha}")
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.0,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    return model, tokenizer


def train(args: argparse.Namespace) -> None:
    if not TRAIN_PARQUET.exists() or not EVAL_PARQUET.exists():
        raise SystemExit("Run assemble_sft_corpus.py first.")

    model, tokenizer = build_model(args)
    train_ds, eval_ds = load_datasets(tokenizer)

    OUT_TRAINER.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(OUT_TRAINER),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=200,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=is_bfloat16_supported(),
        fp16=not is_bfloat16_supported(),
        optim="adamw_8bit",
        weight_decay=0.0,
        seed=42,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        args=training_args,
        packing=False,
    )

    # Mask loss on everything before the model's response
    trainer = train_on_responses_only(
        trainer,
        instruction_part=INSTRUCTION_PART,
        response_part=RESPONSE_PART,
    )

    print(f"\n[train] starting — effective batch size = {args.batch_size * args.grad_accum}")
    print(f"[train] epochs={args.epochs}  lr={args.learning_rate}  max_seq={args.max_seq_length}")

    if args.resume:
        trainer.train(resume_from_checkpoint=True)
    else:
        trainer.train()

    print("\n[save] LoRA adapter ->", OUT_LORA)
    OUT_LORA.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUT_LORA))
    tokenizer.save_pretrained(str(OUT_LORA))

    if args.save_merged:
        print("[save] merging + saving FP16 ->", OUT_MERGED)
        OUT_MERGED.mkdir(parents=True, exist_ok=True)
        model.save_pretrained_merged(
            str(OUT_MERGED), tokenizer, save_method="merged_16bit"
        )

    print("\n[done] Next: python -m src.sft_v3.eval_judge")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base-model", default=DEFAULT_BASE)
    p.add_argument("--epochs", type=float, default=2.0)
    p.add_argument("--batch-size", type=int, default=2)
    p.add_argument("--grad-accum", type=int, default=8)
    p.add_argument("--max-seq-length", type=int, default=4096)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--learning-rate", type=float, default=2e-4)
    p.add_argument("--save-merged", action="store_true",
                   help="Also export FP16 merged weights to gemma-judge-merged/")
    p.add_argument("--resume", action="store_true",
                   help="Resume from latest checkpoint in gemma-judge-trainer/")
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())