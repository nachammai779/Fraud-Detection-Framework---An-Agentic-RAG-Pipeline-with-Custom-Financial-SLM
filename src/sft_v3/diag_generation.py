"""Minimal generation diagnostic for the trained Gemma-judge merged model.

Run on the pod after training to verify generation works end-to-end.

  python -m src.sft_v3.diag_generation
"""
import torch
from unsloth import FastLanguageModel

MODEL_DIR = "data/sft_v3/gemma-judge-merged"

print("[load] loading model from", MODEL_DIR)
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_DIR,
    max_seq_length=4096,
    dtype=None,
    load_in_4bit=False,
)
FastLanguageModel.for_inference(model)
# Unwrap the multimodal processor to the text tokenizer
if hasattr(tokenizer, "tokenizer"):
    print("[unwrap] using underlying text tokenizer")
    tokenizer = tokenizer.tokenizer

print("\n[tokenizer config]")
print("  eos_token:", repr(tokenizer.eos_token), "id:", tokenizer.eos_token_id)
print("  pad_token:", repr(tokenizer.pad_token), "id:", tokenizer.pad_token_id)
print("  bos_token:", repr(tokenizer.bos_token), "id:", getattr(tokenizer, "bos_token_id", None))

messages = [{"role": "user", "content": "What is 2 + 2? Answer in one sentence."}]
inputs = tokenizer.apply_chat_template(
    messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
).to("cuda")

print("\n[input]")
print("  shape:", inputs.shape)
print("  last 8 token ids:", inputs[0, -8:].tolist())
print("  decoded prompt (special tokens visible):")
print("  " + repr(tokenizer.decode(inputs[0], skip_special_tokens=False)))

print("\n[generate] max_new_tokens=30, greedy")
out = model.generate(
    input_ids=inputs,
    max_new_tokens=30,
    do_sample=False,
)
new_count = out.shape[1] - inputs.shape[1]
print("  output shape:", out.shape, "  new tokens:", new_count)

if new_count > 0:
    new_ids = out[0, inputs.shape[1]:]
    print("  new token ids:", new_ids.tolist())
    print("  decoded (special tokens visible):")
    print("  " + repr(tokenizer.decode(new_ids, skip_special_tokens=False)))
    print("  decoded (special tokens stripped):")
    print("  " + repr(tokenizer.decode(new_ids, skip_special_tokens=True)))
else:
    print("  ZERO new tokens generated — model emitted nothing.")