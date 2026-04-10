"""
tabddpm_generator.py
====================
Hybrid synthetic transaction generator:
    - Tab-DDPM (Gaussian diffusion) for NUMERICAL columns
    - Profile-weighted sampling for CATEGORICAL columns
    - Correlation logic ties categoricals to numericals

This hybrid approach avoids the multinomial diffusion mode-collapse issue
where Tab-DDPM collapses to one dominant category on small datasets.

Pipeline per archetype:
    1. Build seed training data from profile behavioral distributions
    2. Train Gaussian-only diffusion on numerical features
    3. Sample synthetic numericals from diffusion model
    4. Sample categoricals from profile distributions with correlation
    5. Post-process: attach UUIDs, timestamps, schema fields
    6. Write to datasets/{archetype}/synthetic/transactions.parquet

Usage:
    python tabddpm_generator.py
    python tabddpm_generator.py --archetypes remittance gig_worker
    python tabddpm_generator.py --samples_per_archetype 5000 --epochs 700
"""

import sys
import os
import uuid
import argparse
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from datetime import datetime, timezone, timedelta

# Add project paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lib", "tab-ddpm"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "scrapers"))

from tab_ddpm import GaussianMultinomialDiffusion
from tab_ddpm.modules import MLPDiffusion
from profile_configs import PROFILES, get_profile
from schema import ARCHETYPES

# ── Column definitions ───────────────────────────────────────────────────────

NUMERICAL_COLS = [
    "transaction_amount_usd",
    "fee_amount_usd",
    "sender_age",
    "hour_of_day",
    "day_of_week",
    "days_since_last_txn",
    "account_age_days",
    "txn_count_30d",
]

LABEL_COL = "is_fraud"


# ── Seed data builder ────────────────────────────────────────────────────────

def build_seed_data(profile: dict, n_samples: int = 3000) -> pd.DataFrame:
    """Generate seed training data from a behavioral profile."""
    rng = np.random.default_rng(42)
    tp = profile["transaction_patterns"]
    demo = profile["demographics"]

    fraud_rate = 0.10
    is_fraud = rng.choice([0, 1], size=n_samples, p=[1 - fraud_rate, fraud_rate])
    fraud_mask = is_fraud == 1

    amt_lo, amt_hi = tp["amount_range_usd"]
    amounts = rng.lognormal(mean=np.log(tp["median_amount_usd"]), sigma=0.8, size=n_samples)
    amounts = np.clip(amounts, amt_lo, amt_hi * 1.5)
    amounts[fraud_mask] *= rng.uniform(1.2, 3.0, size=fraud_mask.sum())
    amounts = np.clip(amounts, amt_lo, amt_hi * 2)

    fee_lo, fee_hi = tp.get("typical_fee_pct", (1.0, 10.0))
    fees = amounts * rng.uniform(fee_lo, fee_hi, size=n_samples) / 100.0

    age_lo, age_hi = demo["age_range"]
    ages = rng.integers(age_lo, age_hi + 1, size=n_samples)

    hours = np.clip(rng.normal(loc=np.mean(tp.get("peak_hours", (9, 17))), scale=3.0, size=n_samples), 0, 23).astype(int)
    hours[fraud_mask] = rng.integers(0, 24, size=fraud_mask.sum())

    peak_day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                     "Friday": 4, "Saturday": 5, "Sunday": 6}
    weights = np.ones(7) * 0.1
    for d in tp.get("peak_days", ["Friday"]):
        weights[peak_day_map.get(d, 4)] = 0.25
    weights /= weights.sum()
    dow = rng.choice(7, size=n_samples, p=weights)

    days_since = np.clip(rng.exponential(scale=5.0, size=n_samples), 0, 90).astype(int)

    account_age = rng.integers(30, 2000, size=n_samples)
    account_age[fraud_mask] = rng.integers(1, 180, size=fraud_mask.sum())

    txn_count = rng.poisson(lam=8, size=n_samples)
    txn_count[fraud_mask] = rng.poisson(lam=20, size=fraud_mask.sum())

    return pd.DataFrame({
        "transaction_amount_usd": np.round(amounts, 2),
        "fee_amount_usd": np.round(fees, 2),
        "sender_age": ages,
        "hour_of_day": hours,
        "day_of_week": dow,
        "days_since_last_txn": days_since,
        "account_age_days": account_age,
        "txn_count_30d": txn_count,
        "is_fraud": is_fraud,
    })


# ── Numerical Encoder ────────────────────────────────────────────────────────

class NumericalEncoder:
    """Standardize numerical columns for Gaussian diffusion."""

    def __init__(self, df: pd.DataFrame, num_cols: list):
        self.num_cols = num_cols
        self.num_mean = df[num_cols].mean().values.astype(np.float32)
        self.num_std = df[num_cols].std().values.astype(np.float32)
        self.num_std[self.num_std < 1e-8] = 1.0

    def encode(self, df: pd.DataFrame):
        X_num = (df[self.num_cols].values - self.num_mean) / self.num_std
        X_num = torch.tensor(X_num, dtype=torch.float32)
        y = torch.tensor(df[LABEL_COL].values, dtype=torch.long)
        return X_num, y

    def decode(self, X_num: np.ndarray) -> pd.DataFrame:
        vals = X_num * self.num_std + self.num_mean
        return pd.DataFrame(vals, columns=self.num_cols)


# ── Training (Gaussian-only diffusion) ───────────────────────────────────────

def train_tabddpm(
    df: pd.DataFrame,
    encoder: NumericalEncoder,
    epochs: int = 700,
    lr: float = 1e-3,
    batch_size: int = 256,
    num_timesteps: int = 500,
    device: str = "cpu",
):
    """Train Gaussian-only Tab-DDPM on numerical features."""
    X_num, y = encoder.encode(df)
    n_num = X_num.shape[1]
    num_label_classes = df[LABEL_COL].nunique()

    # No categorical classes — pure Gaussian diffusion
    num_classes_array = np.array([0])

    denoise_fn = MLPDiffusion(
        d_in=n_num,
        num_classes=num_label_classes,
        is_y_cond=True,
        rtdl_params={"d_layers": [256, 256, 256], "dropout": 0.1},
        dim_t=128,
    ).to(device)

    model = GaussianMultinomialDiffusion(
        num_classes=num_classes_array,
        num_numerical_features=n_num,
        denoise_fn=denoise_fn,
        num_timesteps=num_timesteps,
        gaussian_loss_type="mse",
        scheduler="cosine",
        device=torch.device(device),
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    dataset = torch.utils.data.TensorDataset(X_num, y)
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        n_batches = 0
        for batch_num, batch_y in loader:
            batch_num = batch_num.to(device)
            batch_y = batch_y.to(device)

            out_dict = {"y": batch_y}
            loss_multi, loss_gauss = model.mixed_loss(batch_num, out_dict)
            loss = (loss_multi + loss_gauss).mean()

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

        if (epoch + 1) % 100 == 0 or epoch == 0:
            avg = epoch_loss / max(n_batches, 1)
            print(f"    Epoch {epoch+1:>4d}/{epochs} | loss={avg:.4f}")

    return model


# ── Categorical sampler (profile-weighted + correlated) ──────────────────────

def sample_categoricals(profile: dict, n_samples: int, is_fraud: np.ndarray) -> pd.DataFrame:
    """Sample categorical columns from profile distributions with correlation."""
    rng = np.random.default_rng()

    # Fraud vector — from profile distribution
    vectors = list(profile["fraud_vectors"].keys())
    vp = np.array(list(profile["fraud_vectors"].values()))
    vp /= vp.sum()
    fraud_vectors = rng.choice(vectors, size=n_samples, p=vp)

    # Language — from profile distribution
    langs = list(profile["language_mix"].keys())
    lp = np.array(list(profile["language_mix"].values()))
    lp /= lp.sum()
    languages = rng.choice(langs, size=n_samples, p=lp)

    # Instrument — from profile list (uniform, with slight fraud bias)
    instruments = profile["instruments"]
    inst_weights = np.ones(len(instruments))
    inst_weights /= inst_weights.sum()
    instrument_choice = rng.choice(instruments, size=n_samples, p=inst_weights)

    return pd.DataFrame({
        "fraud_vector": fraud_vectors,
        "language": languages,
        "instrument": instrument_choice,
    })


# ── Sampling & post-processing ───────────────────────────────────────────────

def generate_synthetic(
    model: GaussianMultinomialDiffusion,
    encoder: NumericalEncoder,
    archetype: str,
    profile: dict,
    n_samples: int = 5000,
    batch_size: int = 500,
    device: str = "cpu",
) -> pd.DataFrame:
    """Sample numericals from diffusion, categoricals from profile, merge."""
    model.eval()

    y_dist = torch.tensor([0.90, 0.10])

    with torch.no_grad():
        x_gen, y_gen = model.sample_all(n_samples, batch_size, y_dist, ddim=False)

    x_gen = x_gen.numpy()
    y_gen = y_gen.numpy()

    # Decode numericals
    df_num = encoder.decode(x_gen)

    # Sample categoricals from profile distributions
    df_cat = sample_categoricals(profile, n_samples, y_gen)

    df = pd.concat([df_num, df_cat], axis=1)
    df["is_fraud"] = y_gen

    # Post-process: clamp and round
    tp = profile["transaction_patterns"]
    amt_lo, amt_hi = tp["amount_range_usd"]
    df["transaction_amount_usd"] = df["transaction_amount_usd"].clip(amt_lo, amt_hi * 2).round(2)
    df["fee_amount_usd"] = df["fee_amount_usd"].clip(0, amt_hi).round(2)
    df["sender_age"] = df["sender_age"].clip(*profile["demographics"]["age_range"]).astype(int)
    df["hour_of_day"] = df["hour_of_day"].clip(0, 23).astype(int)
    df["day_of_week"] = df["day_of_week"].clip(0, 6).astype(int)
    df["days_since_last_txn"] = df["days_since_last_txn"].clip(0, 90).astype(int)
    df["account_age_days"] = df["account_age_days"].clip(1, 2000).astype(int)
    df["txn_count_30d"] = df["txn_count_30d"].clip(0, 100).astype(int)

    # ── Add universal schema fields ──────────────────────────────────────
    df.insert(0, "data_uuid", [str(uuid.uuid4()) for _ in range(len(df))])
    df.insert(1, "id", [f"synth_{uuid.uuid4().hex[:12]}" for _ in range(len(df))])
    df.insert(2, "archetype", archetype)

    df["fraud_vector_hint"] = df["fraud_vector"]
    df["detected_language_hints"] = df["language"].apply(lambda x: [x])
    df["narrative_text"] = ""  # placeholder for Adaptive Data

    base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    timestamps = [
        (base_date + timedelta(
            days=int(np.random.randint(0, 365)),
            hours=int(row["hour_of_day"]),
            minutes=int(np.random.randint(0, 60)),
        )).isoformat()
        for _, row in df.iterrows()
    ]
    df["record_timestamp"] = timestamps
    df["source"] = "tabddpm_synthetic"

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    df["day_of_week_name"] = df["day_of_week"].map(lambda x: day_names[x])

    # Reorder columns
    universal = ["data_uuid", "id", "archetype", "source", "narrative_text",
                 "detected_language_hints", "fraud_vector_hint", "record_timestamp"]
    txn_cols = ["transaction_amount_usd", "fee_amount_usd", "sender_age",
                "hour_of_day", "day_of_week", "day_of_week_name",
                "days_since_last_txn", "account_age_days", "txn_count_30d",
                "fraud_vector", "language", "instrument", "is_fraud"]
    df = df[universal + txn_cols]

    return df


# ── Full pipeline ────────────────────────────────────────────────────────────

def run_archetype(
    archetype: str,
    output_dir: str = "datasets",
    seed_size: int = 3000,
    n_samples: int = 5000,
    epochs: int = 700,
    device: str = "cpu",
):
    """Full pipeline for one archetype."""
    print(f"\n{'='*60}")
    print(f"Tab-DDPM Hybrid Generator: {archetype.upper()}")
    print(f"{'='*60}")

    profile = get_profile(archetype)
    print(f"  Description: {profile['description']}")
    print(f"  Seed: {seed_size} | Target: {n_samples} | Epochs: {epochs}")
    print(f"  Mode: Gaussian diffusion (numericals) + profile sampling (categoricals)")

    # Step 1: Build seed
    print("\n  [1/4] Building seed training data...")
    df_seed = build_seed_data(profile, n_samples=seed_size)
    print(f"    Shape: {df_seed.shape} | Fraud rate: {df_seed['is_fraud'].mean():.1%}")

    # Step 2: Encode numericals only
    print("  [2/4] Encoding numerical features...")
    encoder = NumericalEncoder(df_seed, NUMERICAL_COLS)
    print(f"    {len(NUMERICAL_COLS)} numerical columns")

    # Step 3: Train
    print(f"  [3/4] Training Gaussian diffusion ({epochs} epochs, device={device})...")
    model = train_tabddpm(df_seed, encoder, epochs=epochs, device=device)

    # Step 4: Generate
    print(f"  [4/4] Generating {n_samples} synthetic records...")
    df_synth = generate_synthetic(model, encoder, archetype, profile,
                                   n_samples=n_samples, device=device)

    # Save
    out_dir = os.path.join(output_dir, archetype, "synthetic")
    os.makedirs(out_dir, exist_ok=True)

    parquet_path = os.path.join(out_dir, "transactions.parquet")
    df_synth.to_parquet(parquet_path, index=False, engine="pyarrow")

    csv_path = os.path.join(out_dir, f"transactions_{archetype}.csv")
    df_synth.to_csv(csv_path, index=False)

    # Stats
    stats = {
        "archetype": archetype,
        "total_synthetic_records": len(df_synth),
        "fraud_rate": float(df_synth["is_fraud"].mean()),
        "seed_size": seed_size,
        "epochs_trained": epochs,
        "generation_mode": "hybrid (Gaussian diffusion + profile categorical sampling)",
        "numerical_columns": NUMERICAL_COLS,
        "amount_stats": {
            "mean": float(df_synth["transaction_amount_usd"].mean()),
            "median": float(df_synth["transaction_amount_usd"].median()),
            "min": float(df_synth["transaction_amount_usd"].min()),
            "max": float(df_synth["transaction_amount_usd"].max()),
        },
        "fraud_vector_distribution": df_synth["fraud_vector"].value_counts().to_dict(),
        "language_distribution": df_synth["language"].value_counts().to_dict(),
        "instrument_distribution": df_synth["instrument"].value_counts().to_dict(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_files": {"parquet": parquet_path, "csv": csv_path},
    }
    stats_path = os.path.join(out_dir, "generation_summary.json")
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n  -> Parquet: {parquet_path}")
    print(f"  -> CSV: {csv_path}")
    print(f"  -> Fraud rate: {stats['fraud_rate']:.1%}")
    print(f"  -> Amount median: ${stats['amount_stats']['median']:.0f}")
    print(f"  -> Vectors: {df_synth['fraud_vector'].nunique()} | Languages: {df_synth['language'].nunique()} | Instruments: {df_synth['instrument'].nunique()}")

    return df_synth, stats


def run_all(
    output_dir: str = "datasets",
    archetypes: list = None,
    seed_size: int = 3000,
    n_samples: int = 5000,
    epochs: int = 700,
    device: str = "cpu",
):
    """Run generation for all archetypes."""
    targets = archetypes or list(ARCHETYPES)

    print("=" * 60)
    print("Tab-DDPM Hybrid Synthetic Transaction Generator")
    print("  Numericals: Gaussian diffusion")
    print("  Categoricals: Profile-weighted sampling")
    print("=" * 60)
    print(f"Archetypes: {targets}")
    print(f"Samples per archetype: {n_samples}")
    print(f"Device: {device}\n")

    all_stats = []
    for arch in targets:
        _, stats = run_archetype(arch, output_dir=output_dir, seed_size=seed_size,
                                  n_samples=n_samples, epochs=epochs, device=device)
        all_stats.append(stats)

    print(f"\n{'='*60}")
    print("GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"{'Archetype':<15} {'Records':<10} {'Fraud%':<10} {'Median$':<10} {'Vectors':<10} {'Langs':<8} {'Instr'}")
    print("-" * 70)
    for s in all_stats:
        vecs = len(s["fraud_vector_distribution"])
        lngs = len(s["language_distribution"])
        inst = len(s["instrument_distribution"])
        print(f"{s['archetype']:<15} {s['total_synthetic_records']:<10} "
              f"{s['fraud_rate']:.1%}{'':5} ${s['amount_stats']['median']:<8.0f} "
              f"{vecs:<10} {lngs:<8} {inst}")


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tab-DDPM hybrid synthetic transaction generator")
    parser.add_argument("--output_dir", default="datasets")
    parser.add_argument("--archetypes", nargs="+", choices=list(ARCHETYPES))
    parser.add_argument("--samples_per_archetype", type=int, default=5000)
    parser.add_argument("--seed_size", type=int, default=3000)
    parser.add_argument("--epochs", type=int, default=700)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    run_all(output_dir=args.output_dir, archetypes=args.archetypes,
            seed_size=args.seed_size, n_samples=args.samples_per_archetype,
            epochs=args.epochs, device=args.device)
