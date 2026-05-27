"""Shared prompt builder for v3 SFT (Gemma-as-judge).

Used by:
  - prepare_cot_dataset.py     (builds {prompt, completion} from v4 CoT)
  - prepare_qwen_input.py      (builds prompts for Qwen distillation)
  - qwen_distill.py            (re-uses build_prompt at inference time)
  - train_lora.py              (chat-template wrapping)
"""

SYSTEM_PROMPT = (
    "You are an expert financial fraud analyst. Given a transaction record, "
    "a first-person narrative, persona context, and the candidate fraud vector, "
    "produce a structured chain-of-thought analysis and verdict. "
    "Follow the section format exactly."
)

OUTPUT_FORMAT_SPEC = """Produce the analysis using this exact format:

### 1. Signal Identification
[Extract anomalies and corroborating facts from the narrative and tabular features.]

### 2. Behavioral Baseline Comparison
[Compare against the persona's expected envelope for this archetype.]

### 3. Fraud Vector Assessment
[Assess whether the candidate fraud vector fits; consider alternatives.]

### 4. Verdict
verdict: <fraud | not_fraud>
confidence: <0.0-1.0>
key_signals: [comma-separated top 3-5 signals driving the verdict]
typology_code: <typology label or null>"""


def build_user_prompt(row: dict) -> str:
    """Build the USER turn from a normalized row.

    Row must contain keys: archetype, narrative_text, fraud_vector_hint,
    transaction_amount_usd, instrument, hour_of_day, day_of_week_name,
    days_since_last_txn, account_age_days, txn_count_30d, device_type,
    device_stability, language, sender_age, persona_id, fee_amount_usd.
    Missing values become 'unknown'.
    """
    g = lambda k: row.get(k, "unknown") if row.get(k) is not None else "unknown"
    return (
        "## Transaction Record\n"
        f"- archetype: {g('archetype')}\n"
        f"- amount_usd: {g('transaction_amount_usd')}\n"
        f"- fee_usd: {g('fee_amount_usd')}\n"
        f"- instrument: {g('instrument')}\n"
        f"- hour_of_day: {g('hour_of_day')}\n"
        f"- day_of_week: {g('day_of_week_name')}\n"
        f"- days_since_last_txn: {g('days_since_last_txn')}\n"
        f"- account_age_days: {g('account_age_days')}\n"
        f"- txn_count_30d: {g('txn_count_30d')}\n"
        f"- device_type: {g('device_type')}\n"
        f"- device_stability: {g('device_stability')}\n"
        f"- language: {g('language')}\n"
        "\n## Persona Context\n"
        f"- sender_age: {g('sender_age')}\n"
        f"- persona_id: {g('persona_id')}\n"
        "\n## Narrative (first-person account)\n"
        f"{g('narrative_text')}\n"
        "\n## Candidate Fraud Vector\n"
        f"{g('fraud_vector_hint')}\n"
        "\n## Task\n"
        "Analyze the transaction against behavioral baselines for this archetype.\n\n"
        f"{OUTPUT_FORMAT_SPEC}"
    )


def build_chat_messages(row: dict) -> list[dict]:
    """Return chat-template messages list (system + user). Caller appends assistant."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(row)},
    ]