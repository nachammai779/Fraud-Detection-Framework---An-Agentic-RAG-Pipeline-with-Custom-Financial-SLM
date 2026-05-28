"""Test generation on the BASE Gemma 4 E4B-it (untrained) to isolate whether
the all-pad-tokens issue is in our merged checkpoint or in the loading stack.

  python -m src.sft_v3.diag_base
"""
from unsloth import FastLanguageModel

print("[load] base google/gemma-4-E4B-it (untrained)")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="google/gemma-4-E4B-it",
    max_seq_length=4096,
    dtype=None,
    load_in_4bit=True,
)
FastLanguageModel.for_inference(model)
if hasattr(tokenizer, "tokenizer"):
    tokenizer = tokenizer.tokenizer

inputs = tokenizer.apply_chat_template(
    [{"role": "user", "content": "What is 2 + 2? Answer in one sentence."}],
    tokenize=True, add_generation_prompt=True, return_tensors="pt",
).to("cuda")

out = model.generate(input_ids=inputs, max_new_tokens=30, do_sample=False)
new = out[0, inputs.shape[1]:]
print("new ids:", new.tolist())
print("decoded (skip special):", repr(tokenizer.decode(new, skip_special_tokens=True)))
print("decoded (with special):", repr(tokenizer.decode(new, skip_special_tokens=False)))