"""
Tab-DDPM v2 — persona-conditioned synthetic transaction generator.

Per-persona sampling driven by the Adaption Expand-World conditioning schema
(transaction_calendar, remittance_cadence, income_seasonality, device_fingerprint_evolution).
Each generated row carries persona_id, so the downstream persona_verify pipeline
has a real anchor to score coherence against.

Design choice: the conditioning schema is rich enough per persona that we sample
directly from its parameters (amount bands, channels, day-of-week/hour windows,
cadences) rather than training a diffusion model per persona. Numerical jitter
uses a lognormal/gaussian perturbation on the schema-stated mean/range; this
preserves the "Gaussian diffusion for numerics" spirit of v1 while respecting
per-persona conditioning.

Inputs:
  datasets_v2/{archetype}/personas/persona_profiles.json
  datasets_v2/{archetype}/expanded_world/conditioning_schema.parquet

Output:
  datasets_v2/{archetype}/synthetic/transactions.parquet
  datasets_v2/{archetype}/synthetic/transactions_{archetype}.csv
  datasets_v2/{archetype}/synthetic/generation_summary.json

Usage:
  python src/generators/tabddpm_v2_generator.py --all
  python src/generators/tabddpm_v2_generator.py --archetype remittance --samples_per_archetype 5000
"""

import argparse
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "datasets_v2"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DEFAULT_FRAUD_VECTORS = {
    "remittance": ["wire transfer", "emergency", "estafa", "interception", "exchange rate"],
    "gig_worker": ["ATO", "SIM swap", "OTP", "stolen", "fake support"],
    "unbanked": ["predatory", "prepaid", "kiosk", "advance fee", "fake loan", "hawala"],
    "itin": ["ITIN", "EIN", "identity theft", "synthetic identity", "tax return"],
}


# ── Conditioning-schema param extraction ─────────────────────────────────────


def _safe_load(raw: str) -> dict | None:
    if not raw or raw == "null":
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None


CHANNEL_KEYS = {"channel", "network", "primary", "source", "venue_types",
                 "card_bin_prefix", "platform", "kiosk", "service"}


def _walk_channels(node, acc: list):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in CHANNEL_KEYS and isinstance(v, str):
                acc.append(v)
            elif k in CHANNEL_KEYS and isinstance(v, list):
                acc.extend([x for x in v if isinstance(x, str)])
            else:
                _walk_channels(v, acc)
    elif isinstance(node, list):
        for item in node:
            _walk_channels(item, acc)


def extract_params(persona: dict, cond: dict) -> dict:
    """Fold persona profile + conditioning schema into a flat sampling spec."""
    tc = (cond or {}).get("transaction_calendar") or {}
    rc = (cond or {}).get("remittance_cadence") or {}
    iso = (cond or {}).get("income_seasonality") or {}
    dev = (cond or {}).get("device_fingerprint_evolution") or {}

    windows = tc.get("recurring_windows") or tc.get("windows") or tc.get("transaction_types") or []

    amount_samples = []
    channels = []
    hour_ranges = []  # list of (start_hour, end_hour)
    peak_days = []
    sub_cadences = []  # list of {"days_between": (lo, hi), "weight": float}

    # Per-platform schedules: joint platform + hour + amount + cadence
    platform_schedules = {}  # {name: {"hours": [(s,e)], "weight": float, "amount": (lo,hi), "cadence": (lo,hi), "fee": float|None}}

    # Schema variant: active_windows with per-platform time_range (gig_003 style)
    for aw in (tc.get("active_windows") or []):
        plat = aw.get("platform")
        if not plat:
            continue
        tr = aw.get("time_range", "")
        hrs = []
        if "-" in tr and ":" in tr:
            try:
                parts = tr.replace(" ", "").split("-")
                h_s, h_e = int(parts[0].split(":")[0]), int(parts[1].split(":")[0])
                hrs = [(h_s, min(h_e, 23) if h_e >= h_s else 23)]
            except (ValueError, IndexError):
                pass
        platform_schedules.setdefault(plat, {"hours": [], "weight": 0.5, "amount": None, "cadence": None, "fee": None})
        if hrs:
            platform_schedules[plat]["hours"].extend(hrs)

    # Schema variant: shift_profile with peak_hours + platform_distribution (gig_004 style)
    sp = tc.get("shift_profile") or {}
    tc_plat_dist = tc.get("platform_distribution") or {}
    if sp.get("weekday_peak_hours"):
        wph = sp["weekday_peak_hours"]
        h_range = (min(wph), max(wph))
        for plat, wt in tc_plat_dist.items():
            platform_schedules.setdefault(plat, {"hours": [], "weight": float(wt), "amount": None, "cadence": None, "fee": None})
            platform_schedules[plat]["hours"].append(h_range)

    # Enrich platform_schedules from rc.income_distribution (gig_003 style)
    rc_income_dist = rc.get("income_distribution") or {}
    for plat, info in rc_income_dist.items():
        if not isinstance(info, dict):
            continue
        ps = platform_schedules.setdefault(plat, {"hours": [], "weight": 0.5, "amount": None, "cadence": None, "fee": None})
        ps["weight"] = float(info.get("weight", ps["weight"]))
        avg = info.get("avg_transaction_usd")
        if avg is not None:
            vol = float(info.get("volatility_coefficient", 0.2))
            a = float(avg)
            ps["amount"] = (a * (1 - vol), a * (1 + vol))
        interval = info.get("interval_days")
        if interval is not None:
            d = int(interval)
            ps["cadence"] = (max(0, d - 1), d + 1)

    # Enrich from rc.platform_distribution weights (gig_001 style)
    rc_plat_dist = rc.get("platform_distribution") or {}
    for plat, wt in rc_plat_dist.items():
        if plat in platform_schedules:
            platform_schedules[plat]["weight"] = float(wt)
        elif isinstance(wt, (int, float)):
            platform_schedules.setdefault(plat, {"hours": [], "weight": float(wt), "amount": None, "cadence": None, "fee": None})

    # Gig-worker style: peak_activity_windows for hours (global, no per-platform — gig_001)
    for paw in (tc.get("peak_activity_windows") or []):
        try:
            h_start = int(str(paw.get("start", "")).split(":")[0])
            h_end = int(str(paw.get("end", "")).split(":")[0])
            if h_end < h_start:
                h_end = 23
            hour_ranges.append((h_start, h_end))
        except (ValueError, IndexError):
            pass
    # If we have platform_schedules but no global hour_ranges, derive from schedules
    if not hour_ranges and platform_schedules:
        for ps in platform_schedules.values():
            hour_ranges.extend(ps["hours"])

    # Gig-worker / unbanked: amounts + channels + cadence from remittance_cadence
    rc_chunk = rc.get("transaction_chunk_usd") or {}
    if isinstance(rc_chunk, dict) and "min" in rc_chunk and "max" in rc_chunk:
        amount_samples.append((float(rc_chunk["min"]), float(rc_chunk["max"])))
    rc_methods = rc.get("method") or []
    if isinstance(rc_methods, list):
        channels.extend([m for m in rc_methods if isinstance(m, str)])
    rc_plat_keys = list(rc_plat_dist.keys()) if rc_plat_dist else []
    if rc_plat_keys and not channels:
        channels.extend(rc_plat_keys)
    rc_freq = rc.get("frequency_per_day") or {}
    if isinstance(rc_freq, dict) and "min" in rc_freq:
        sub_cadences.append({"days_between": (0, 1), "weight": 1.0})
    for w in windows:
        a = w.get("amount_usd") or {}
        if isinstance(a, dict) and "min" in a and "max" in a:
            amount_samples.append((float(a["min"]), float(a["max"])))
        elif isinstance(a, (int, float)):
            amount_samples.append((float(a) * 0.8, float(a) * 1.2))
        ch = w.get("channel") or (w.get("channel_selection_logic") or {}).get("primary")
        if ch:
            channels.append(ch)
        slot = w.get("time_slot_est") or w.get("time_slot")
        if isinstance(slot, str) and "-" in slot and ":" in slot:
            try:
                parts = slot.replace(" ", "").split("-")
                h_start = int(parts[0].split(":")[0])
                h_end = int(parts[1].split(":")[0])
                hour_ranges.append((h_start, h_end))
            except (ValueError, IndexError):
                pass
        elif isinstance(slot, str) and ":" in slot:
            try:
                h = int(slot.split(":")[0].strip())
                hour_ranges.append((max(0, h - 1), min(23, h + 1)))
            except ValueError:
                pass
        dow = w.get("day_of_week")
        if isinstance(dow, str) and dow in DAY_NAMES:
            peak_days.append(DAY_NAMES.index(dow))
        wtype = (w.get("type") or "").lower()
        if "daily" in wtype:
            sub_cadences.append({"days_between": (0, 2), "weight": 1.0})
        elif "weekly" in wtype:
            sub_cadences.append({"days_between": (5, 9), "weight": 1.0})
        elif "biweekly" in wtype:
            sub_cadences.append({"days_between": (12, 16), "weight": 1.0})
        elif "monthly" in wtype:
            sub_cadences.append({"days_between": (25, 35), "weight": 1.0})

    if not amount_samples:
        inc = persona.get("income_usd_weekly") or [200, 500]
        amount_samples = [(float(inc[0]) * 0.2, float(inc[1]) * 0.5)]

    # Cadence: from sub_cadences parsed above, or fallback to remittance_cadence pattern
    if not sub_cadences:
        pattern = (rc.get("pattern") or "").lower()
        if "daily" in pattern:
            sub_cadences = [{"days_between": (0, 2), "weight": 1.0}]
        elif "weekly" in pattern and "biweekly" not in pattern:
            sub_cadences = [{"days_between": (5, 9), "weight": 1.0}]
        elif "biweekly" in pattern:
            sub_cadences = [{"days_between": (12, 16), "weight": 1.0}]
        elif "monthly" in pattern:
            sub_cadences = [{"days_between": (25, 35), "weight": 1.0}]
        # mixed cadence — e.g. "weekly small + monthly large"
        if "weekly" in pattern and "monthly" in pattern:
            sub_cadences = [
                {"days_between": (5, 9), "weight": 0.65},
                {"days_between": (25, 35), "weight": 0.35},
            ]
    if not sub_cadences:
        sub_cadences = [{"days_between": (3, 14), "weight": 1.0}]
    cadence_days = sub_cadences[0]["days_between"]  # backwards compat

    # Seasonality quarterly modifiers
    modifiers = (iso.get("construction_cycle_modifiers")
                 or iso.get("quarterly_modifiers")
                 or iso.get("seasonal_modifiers") or {})
    quarterly = {q: float(modifiers.get(q, 1.0)) for q in ("Q1", "Q2", "Q3", "Q4")}

    hw = dev.get("hardware_profile") if isinstance(dev, dict) else None
    if not isinstance(hw, dict):
        hw = {}
    device_type = hw.get("device_type") or persona.get("device", "Android")
    try:
        stability = float(hw.get("stability_score", 0.7))
    except (TypeError, ValueError):
        stability = 0.7

    age = int(persona.get("age", 35))
    languages = persona.get("language_mix") or ["en"]

    if not channels:
        _walk_channels(cond or {}, channels)
    loyalty = persona.get("transfer_service_loyalty") or {}
    if not channels:
        prepaid = persona.get("prepaid_card_stack") or []
        if prepaid:
            channels = [c for c in prepaid if isinstance(c, str)]
    if not channels:
        channels = [loyalty.get("primary") or persona.get("kiosk_location") or persona.get("business_type") or "cash"]
    channels = [c for c in channels if c]
    if not channels:
        channels = ["cash"]

    loss_tol = persona.get("loss_tolerance_usd")
    try:
        loss_tol = float(loss_tol) if loss_tol is not None else None
    except (TypeError, ValueError):
        loss_tol = None

    return {
        "amount_bands": amount_samples,
        "channels": channels,
        "hour_ranges": hour_ranges or [(9, 12), (17, 20)],
        "peak_days": peak_days or [0, 1, 2, 3, 4],
        "sub_cadences": sub_cadences,
        "cadence_days": cadence_days,
        "quarterly": quarterly,
        "device_type": device_type,
        "device_stability": stability,
        "age": age,
        "languages": languages,
        "loss_tolerance_usd": loss_tol,
        "platform_schedules": platform_schedules,
    }


# ── Per-persona sampler ──────────────────────────────────────────────────────


def sample_persona(persona: dict, cond: dict, n_samples: int, archetype: str,
                   rng: np.random.Generator) -> pd.DataFrame:
    params = extract_params(persona, cond)

    fraud_vectors = DEFAULT_FRAUD_VECTORS[archetype]
    fraud_rate = 0.10
    is_fraud = rng.choice([0, 1], size=n_samples, p=[1 - fraud_rate, fraud_rate])
    fraud_mask = is_fraud == 1

    # Amounts: per-row pick a band, sample lognormally within it
    band_idx = rng.integers(0, len(params["amount_bands"]), size=n_samples)
    lows = np.array([params["amount_bands"][i][0] for i in band_idx])
    highs = np.array([params["amount_bands"][i][1] for i in band_idx])
    mu = np.log(np.clip((lows + highs) / 2.0, 1.0, None))
    amounts = rng.lognormal(mean=mu, sigma=0.25)
    amounts = np.clip(amounts, lows * 0.7, highs * 1.5)
    # Cap non-fraud amounts at loss_tolerance; fraud can exceed
    loss_tol = params.get("loss_tolerance_usd")
    if loss_tol is not None:
        legit_mask = ~fraud_mask
        amounts[legit_mask] = np.minimum(amounts[legit_mask], loss_tol * 1.1)
    amounts[fraud_mask] *= rng.uniform(1.5, 3.5, size=fraud_mask.sum())

    # Fees: use persona's stated fee if available, else archetype defaults
    rc_fee = (cond or {}).get("remittance_cadence") or {}
    stated_fee = rc_fee.get("fee_per_transaction_usd")
    if stated_fee is not None:
        try:
            base_fee = float(stated_fee)
            fees = np.full(n_samples, base_fee) + rng.normal(0, 0.10, size=n_samples)
            fees = np.clip(fees, base_fee * 0.5, base_fee * 2.0)
        except (TypeError, ValueError):
            fees = amounts * rng.uniform(0.02, 0.05, size=n_samples)
    elif archetype in ("remittance", "unbanked"):
        fees = amounts * rng.uniform(0.02, 0.05, size=n_samples)
    else:
        fees = np.where(
            amounts < 500,
            rng.uniform(1.49, 2.99, size=n_samples),
            amounts * rng.uniform(0.005, 0.02, size=n_samples),
        )

    # Joint platform → hour → amount → cadence sampling
    plat_scheds = params.get("platform_schedules") or {}

    if plat_scheds:
        # Build weighted platform list
        plat_names = list(plat_scheds.keys())
        plat_weights = np.array([plat_scheds[p]["weight"] for p in plat_names])
        plat_weights /= plat_weights.sum()
        plat_idx = rng.choice(len(plat_names), size=n_samples, p=plat_weights)

        channels = np.array([plat_names[pi] for pi in plat_idx])
        hours = np.zeros(n_samples, dtype=int)
        for i in range(n_samples):
            ps = plat_scheds[plat_names[plat_idx[i]]]
            if ps["hours"]:
                hr = rng.choice(len(ps["hours"]))
                h_s, h_e = ps["hours"][hr]
                hours[i] = rng.integers(h_s, max(h_s + 1, h_e) + 1)
            else:
                # fallback to global hour_ranges
                hr_ranges = params["hour_ranges"]
                ri = rng.integers(0, len(hr_ranges))
                hours[i] = rng.integers(hr_ranges[ri][0], max(hr_ranges[ri][0] + 1, hr_ranges[ri][1]) + 1)
            # Per-platform amount override
            if ps["amount"] is not None:
                lo, hi = ps["amount"]
                amt = rng.lognormal(np.log(max((lo + hi) / 2, 1)), 0.15)
                amounts[i] = np.clip(amt, lo * 0.8, hi * 1.3)
            # Per-platform cadence override
            if ps["cadence"] is not None:
                c_lo, c_hi = ps["cadence"]
                days_since_arr = rng.integers(c_lo, c_hi + 1)  # scalar, applied below

        jitter = rng.normal(0, 0.3, size=n_samples).astype(int)
        hours = np.clip(hours + jitter, 0, 23).astype(int)
        fraud_hour_shift = rng.integers(-3, 4, size=fraud_mask.sum())
        hours[fraud_mask] = np.clip(hours[fraud_mask] + fraud_hour_shift, 0, 23)

        # Per-platform cadence: rebuild days_since using platform-specific cadence
        days_since = np.zeros(n_samples, dtype=int)
        for i in range(n_samples):
            ps = plat_scheds[plat_names[plat_idx[i]]]
            if ps["cadence"] is not None:
                c_lo, c_hi = ps["cadence"]
                days_since[i] = rng.integers(c_lo, c_hi + 1)
            else:
                sub_cads = params["sub_cadences"]
                cw = np.array([sc["weight"] for sc in sub_cads])
                cw /= cw.sum()
                ci = rng.choice(len(sub_cads), p=cw)
                days_since[i] = rng.integers(sub_cads[ci]["days_between"][0], sub_cads[ci]["days_between"][1] + 1)
    else:
        # Non-platform path: original hour/channel/cadence sampling
        hr_ranges = params["hour_ranges"]
        range_idx = rng.integers(0, len(hr_ranges), size=n_samples)
        hours = np.array([
            rng.integers(hr_ranges[ri][0], max(hr_ranges[ri][0] + 1, hr_ranges[ri][1]) + 1)
            for ri in range_idx
        ])
        jitter = rng.normal(0, 0.5, size=n_samples).astype(int)
        hours = np.clip(hours + jitter, 0, 23).astype(int)
        fraud_hour_shift = rng.integers(-4, 5, size=fraud_mask.sum())
        hours[fraud_mask] = np.clip(hours[fraud_mask] + fraud_hour_shift, 0, 23)

        sub_cads = params["sub_cadences"]
        cad_weights = np.array([sc["weight"] for sc in sub_cads])
        cad_weights /= cad_weights.sum()
        cad_idx = rng.choice(len(sub_cads), size=n_samples, p=cad_weights)
        days_since = np.array([
            rng.integers(sub_cads[ci]["days_between"][0], sub_cads[ci]["days_between"][1] + 1)
            for ci in cad_idx
        ])
        channels = rng.choice(params["channels"], size=n_samples)

    # Day of week: strongly weighted toward peak days
    dow_weights = np.ones(7) * 0.02
    for d in params["peak_days"]:
        dow_weights[d] = 0.4
    dow_weights /= dow_weights.sum()
    dow = rng.choice(7, size=n_samples, p=dow_weights)

    # Languages
    languages = rng.choice(params["languages"], size=n_samples)

    # Timestamps: anchor at 2024, jittered; quarter modifier effect via resampling
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    days_back = rng.integers(0, 365, size=n_samples)
    hours_arr = hours
    timestamps = [
        (now - timedelta(days=int(days_back[i]), hours=int(24 - hours_arr[i]))).replace(
            hour=int(hours_arr[i]), minute=int(rng.integers(0, 60)), second=0
        ).isoformat()
        for i in range(n_samples)
    ]

    # Apply quarterly seasonality to amounts
    quarters = [((now - timedelta(days=int(d))).month - 1) // 3 + 1 for d in days_back]
    q_mods = np.array([params["quarterly"].get(f"Q{q}", 1.0) for q in quarters])
    amounts = amounts * q_mods

    # Sender age with small jitter around persona age
    ages = np.clip(rng.normal(params["age"], 2, size=n_samples), 18, 85).astype(int)

    # Account age: proportional to persona's stated tenure / credit age
    tenure_years = persona.get("sender_tenure_years") or persona.get("credit_file_age_years") or 3
    tenure_mean_days = int(tenure_years * 365)
    account_age = np.clip(
        rng.normal(tenure_mean_days, tenure_mean_days * 0.15, size=n_samples),
        30, tenure_mean_days * 1.3
    ).astype(int)

    # txn_count_30d: derive from cadence (use days_since mean as proxy)
    avg_cadence = float(np.mean(days_since)) if len(days_since) > 0 else 7.0
    expected_30d = max(1, int(30 / max(avg_cadence, 0.5)))
    txn_count_30d = np.clip(
        rng.poisson(expected_30d, size=n_samples), 1, expected_30d * 3
    ).astype(int)

    # Fraud vector: non-fraud uses instrument as label, fraud picks from archetype list
    fv = np.where(
        fraud_mask,
        rng.choice(fraud_vectors, size=n_samples),
        channels,
    )

    df = pd.DataFrame({
        "data_uuid": [str(uuid.uuid4()) for _ in range(n_samples)],
        "id": [f"v2_{archetype}_{uuid.uuid4().hex[:10]}" for _ in range(n_samples)],
        "archetype": archetype,
        "source": "tabddpm_v2_persona_conditioned",
        "persona_id": persona["persona_id"],
        "dataset_version": "v2",
        "narrative_text": "",
        "detected_language_hints": [[str(l)] for l in languages],
        "fraud_vector_hint": fv,
        "record_timestamp": timestamps,
        "transaction_amount_usd": np.round(amounts, 2),
        "fee_amount_usd": np.round(fees, 2),
        "sender_age": ages,
        "hour_of_day": hours.astype(int),
        "day_of_week": dow.astype(int),
        "day_of_week_name": [DAY_NAMES[d] for d in dow],
        "days_since_last_txn": days_since.astype(int),
        "account_age_days": account_age.astype(int),
        "txn_count_30d": txn_count_30d.astype(int),
        "fraud_vector": fv,
        "language": languages,
        "instrument": channels,
        "device_type": params["device_type"],
        "device_stability": params["device_stability"],
        "is_fraud": is_fraud.astype(int),
    })
    return df


# ── Per-archetype orchestrator ───────────────────────────────────────────────


def generate_archetype(archetype: str, samples_per_archetype: int, seed: int) -> dict:
    arch_dir = DATA_ROOT / archetype
    personas = json.loads((arch_dir / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))["personas"]
    cond_df = pd.read_parquet(arch_dir / "expanded_world" / "conditioning_schema.parquet")

    cond_by_pid = {}
    for _, row in cond_df.iterrows():
        cond = {
            "transaction_calendar": _safe_load(row.get("transaction_calendar")),
            "remittance_cadence": _safe_load(row.get("remittance_cadence")),
            "income_seasonality": _safe_load(row.get("income_seasonality")),
            "communication_patterns": _safe_load(row.get("communication_patterns")),
            "device_fingerprint_evolution": _safe_load(row.get("device_fingerprint_evolution")),
        }
        cond_by_pid[row["persona_id"]] = cond

    rng = np.random.default_rng(seed)
    random.seed(seed)

    # Allocate samples across personas, allowing small skew for flavor
    base = samples_per_archetype // len(personas)
    remainder = samples_per_archetype - base * len(personas)
    allocations = [base] * len(personas)
    for i in range(remainder):
        allocations[i] += 1

    frames = []
    for persona, n in zip(personas, allocations):
        cond = cond_by_pid.get(persona["persona_id"], {})
        frames.append(sample_persona(persona, cond, n, archetype, rng))

    df = pd.concat(frames, ignore_index=True)
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    out_dir = arch_dir / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "transactions.parquet"
    df.to_parquet(parquet_path, index=False)
    df.to_csv(out_dir / f"transactions_{archetype}.csv", index=False)

    summary = {
        "archetype": archetype,
        "n_samples": int(len(df)),
        "n_personas": len(personas),
        "per_persona_counts": {p["persona_id"]: int(n) for p, n in zip(personas, allocations)},
        "fraud_rate": float(df["is_fraud"].mean()),
        "mean_amount_usd": float(df["transaction_amount_usd"].mean()),
        "unique_instruments": sorted(df["instrument"].dropna().astype(str).unique().tolist()),
        "unique_languages": sorted(df["language"].dropna().astype(str).unique().tolist()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": "v2",
    }
    (out_dir / "generation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archetype", choices=ARCHETYPES)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--samples_per_archetype", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.all and not args.archetype:
        parser.error("specify --archetype or --all")

    targets = ARCHETYPES if args.all else [args.archetype]
    for arch in targets:
        summary = generate_archetype(arch, args.samples_per_archetype, args.seed)
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
