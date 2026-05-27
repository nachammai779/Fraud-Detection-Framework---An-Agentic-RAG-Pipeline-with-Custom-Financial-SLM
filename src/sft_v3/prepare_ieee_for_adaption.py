"""IEEE-CIS -> Adaption Labs Pass-1 input.

Samples 5,000 fraud + 5,000 non-fraud from IEEE-CIS, derives a coarse archetype
heuristically from ProductCD / P_emaildomain / card6, synthesizes the persona
context (fraud_vector, instrument, language, sender_age) by sampling from
profile_configs, and writes a `for_adaption.jsonl` per archetype that the
existing `src/generators/adaptive_submit.py` flow can ingest.

Heuristic ProductCD -> archetype:
    R -> remittance   (recurring / cross-border-like)
    C -> unbanked     (cash-equivalent)
    S -> gig_worker   (subscription / side-gig fees)
    H -> gig_worker   (hotel/travel proxy for delivery/temp work)
    W -> random across all 4, with bias to itin when P_emaildomain == anonymous.com

Output per archetype:
    datasets/ieee_for_adaption/{archetype}/for_adaption.jsonl
    datasets/ieee_for_adaption/{archetype}/spec.parquet     (sidecar metadata)

Run:
    python -m src.sft_v3.prepare_ieee_for_adaption --n-fraud 5000 --n-nonfraud 5000
"""
from __future__ import annotations
import argparse
import json
import random
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

# Pull archetype catalogs from profile_configs (sibling project module)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scrapers"))
from profile_configs import PROFILES  # type: ignore

IEEE_PATH = Path("Kaggle-IEEE-dataset/train_transaction.csv")
OUT_DIR = Path("datasets/ieee_for_adaption")
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def assign_archetype(product_cd: str, p_email: str | float, rng: random.Random) -> str:
    if product_cd == "R":
        return "remittance"
    if product_cd == "C":
        return "unbanked"
    if product_cd in ("S", "H"):
        return "gig_worker"
    # ProductCD == 'W' fall-through
    if isinstance(p_email, str) and p_email == "anonymous.com":
        # bias toward itin (synthetic identity), but still allow others
        return rng.choices(ARCHETYPES, weights=[0.15, 0.20, 0.20, 0.45], k=1)[0]
    return rng.choice(ARCHETYPES)


def weighted_choice(d: dict, rng: random.Random) -> str:
    keys = list(d.keys())
    weights = list(d.values())
    return rng.choices(keys, weights=weights, k=1)[0]


def build_prompt(archetype: str, fraud_vector: str, instrument: str,
                 amount_usd: float, sender_age: int, language: str,
                 description: str, is_fraud: int) -> str:
    legitimacy = "victim or participant in a fraudulent" if is_fraud else "participant in a legitimate"
    return (
        f"Write a first-person narrative from a {legitimacy} financial transaction. "
        f"Archetype: {archetype}. Fraud vector: {fraud_vector}. "
        f"Financial instrument: {instrument}. Transaction amount: ${amount_usd:.2f}. "
        f"Sender age: {sender_age}. Language: {language}. "
        f"Community context: {description}. "
        "Write 3-5 sentences describing what happened, how the scam worked "
        "(or how the legitimate transaction proceeded), the financial impact, "
        "and the person's emotional response. "
        "Use natural language appropriate for the specified language code."
    )


def main(n_fraud: int, n_nonfraud: int, seed: int) -> None:
    rng = random.Random(seed)
    np.random.seed(seed)

    cols = ["TransactionID", "isFraud", "TransactionAmt", "ProductCD",
            "card4", "card6", "addr1", "P_emaildomain", "R_emaildomain"]
    print(f"[load] {IEEE_PATH}")
    df = pd.read_csv(IEEE_PATH, usecols=cols)
    print(f"  loaded {len(df)} rows ({df.isFraud.sum()} fraud)")

    fraud_pool = df[df.isFraud == 1]
    nonfraud_pool = df[df.isFraud == 0]
    n_fraud = min(n_fraud, len(fraud_pool))
    n_nonfraud = min(n_nonfraud, len(nonfraud_pool))
    sample = pd.concat([
        fraud_pool.sample(n=n_fraud, random_state=seed),
        nonfraud_pool.sample(n=n_nonfraud, random_state=seed),
    ]).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    print(f"[sample] {len(sample)} rows = {n_fraud} fraud + {n_nonfraud} nonfraud")

    # Assign archetype + synthesize persona context per row
    rows_out = {a: [] for a in ARCHETYPES}
    spec_rows = []

    for r in sample.to_dict(orient="records"):
        product_cd = r["ProductCD"]
        p_email = r["P_emaildomain"]
        archetype = assign_archetype(product_cd, p_email, rng)
        profile = PROFILES[archetype]

        fraud_vector = weighted_choice(profile["fraud_vectors"], rng)
        instrument = rng.choice(profile["instruments"])
        language = weighted_choice(profile["language_mix"], rng)
        age_lo, age_hi = profile["demographics"]["age_range"]
        sender_age = rng.randint(age_lo, age_hi)
        amount_usd = float(r["TransactionAmt"])
        is_fraud = int(r["isFraud"])
        data_uuid = str(uuid.uuid4())

        prompt = build_prompt(
            archetype=archetype,
            fraud_vector=fraud_vector,
            instrument=instrument,
            amount_usd=amount_usd,
            sender_age=sender_age,
            language=language,
            description=profile["description"],
            is_fraud=is_fraud,
        )

        rows_out[archetype].append({
            "prompt": prompt,
            "completion": "",
            "data_uuid": data_uuid,
            "archetype": archetype,
            "fraud_vector": fraud_vector,
            "language": language,
            "instrument": instrument,
            "amount_usd": amount_usd,
            "is_fraud": is_fraud,
            "sender_age": sender_age,
            "_source": "ieee_cis",
            "_ieee_transaction_id": int(r["TransactionID"]),
            "_ieee_product_cd": product_cd,
            "_ieee_p_emaildomain": p_email if isinstance(p_email, str) else None,
            "_ieee_card6": r["card6"] if isinstance(r["card6"], str) else None,
        })
        spec_rows.append(rows_out[archetype][-1].copy())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n[write] per-archetype for_adaption.jsonl files:")
    for a in ARCHETYPES:
        sub = OUT_DIR / a
        sub.mkdir(parents=True, exist_ok=True)
        out_path = sub / "for_adaption.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for row in rows_out[a]:
                # only ship adaption-relevant fields in the jsonl
                adaption_row = {k: row[k] for k in [
                    "prompt", "completion", "data_uuid", "archetype",
                    "fraud_vector", "language", "instrument", "amount_usd", "is_fraud",
                ]}
                f.write(json.dumps(adaption_row, ensure_ascii=False) + "\n")
        fraud_n = sum(1 for r in rows_out[a] if r["is_fraud"] == 1)
        print(f"  {a:12s}  {len(rows_out[a]):5d}  (fraud={fraud_n}, nonfraud={len(rows_out[a])-fraud_n})  -> {out_path}")

    spec_df = pd.DataFrame(spec_rows)
    spec_path = OUT_DIR / "spec.parquet"
    spec_df.to_parquet(spec_path, index=False)
    print(f"\n[write] full spec sidecar -> {spec_path}  ({len(spec_df)} rows)")

    print("\n[stats] archetype assignment:")
    print(spec_df["archetype"].value_counts().to_string())
    print("\n[stats] archetype x is_fraud:")
    print(spec_df.groupby(["archetype", "is_fraud"]).size().to_string())
    print("\n[stats] language mix:")
    print(spec_df["language"].value_counts().to_string())
    print("\n[next] upload each for_adaption.jsonl to Adaption Labs, capture dataset_ids,")
    print("       then plug them into src/generators/adaptive_submit.py DATASETS map.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--n-fraud", type=int, default=5000)
    p.add_argument("--n-nonfraud", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    main(args.n_fraud, args.n_nonfraud, args.seed)