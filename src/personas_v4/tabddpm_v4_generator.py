"""
V4 generator — persona-conditioned Tab-DDPM-style sampling with:
  - joint platform -> hour -> amount -> cadence sampling for gig-worker personas
  - per-persona fraud-vector weighting derived from family_crisis_history
  - all five v2 tightening rules (loss-tolerance cap, tight hour jitter,
    realistic fees, cadence-derived txn_count_30d, tenure-derived account age)
  - three v3 universal columns on every row:
      persona_source_ids, behavioral_evidence_grade, fraud_vector_typology_ref

Reads: datasets_v4/{archetype}/personas/persona_profiles.json
       datasets_v4/sources/typology_registry.json
Writes: datasets_v4/{archetype}/synthetic/transactions.parquet

Usage:
  python src/personas_v4/tabddpm_v3_generator.py --all --samples_per_archetype 5000
"""
from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"
TYPOLOGY = json.loads((V4 / "sources" / "typology_registry.json").read_text(encoding="utf-8"))

ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ── Typology resolver ───────────────────────────────────────────────────────

_FRAUD_VECTOR_TO_CODE: dict[str, str] = {}
# SAR advisories first — more specific, citeable advisory codes.
for code, entry in TYPOLOGY.items():
    if code.startswith("SAR_"):
        for vec in entry.get("applies_to_fraud_vectors", []):
            _FRAUD_VECTOR_TO_CODE.setdefault(vec.lower(), code)
for code, entry in TYPOLOGY.items():
    if code.startswith("FTA_"):
        for vec in entry.get("applies_to_fraud_vectors", []):
            _FRAUD_VECTOR_TO_CODE.setdefault(vec.lower(), code)


def resolve_typology(fraud_vector: str | None, is_fraud: int) -> str | None:
    if not is_fraud or not fraud_vector:
        return None
    fv = fraud_vector.strip().lower()
    if fv in _FRAUD_VECTOR_TO_CODE:
        return _FRAUD_VECTOR_TO_CODE[fv]
    for key, code in _FRAUD_VECTOR_TO_CODE.items():
        if key in fv or fv in key:
            return code
    return "FTA_IDENTITY_2024_T1"

# ── Platform reference (stand-in for Adaption Expand-World schemas) ─────────

PLATFORM_DB = {
    "Uber":          {"hours": [(6, 11), (16, 23)],  "amount": (8, 50),   "cadence": (0, 2), "fee_usd": 0.0},
    "Lyft":          {"hours": [(6, 11), (16, 23)],  "amount": (7, 50),   "cadence": (0, 2), "fee_usd": 0.0},
    "Uber Eats":     {"hours": [(11, 14), (18, 23)], "amount": (10, 40),  "cadence": (0, 2), "fee_usd": 0.0},
    "UberEats":      {"hours": [(11, 14), (18, 23)], "amount": (10, 40),  "cadence": (0, 2), "fee_usd": 0.0},
    "DoorDash":      {"hours": [(11, 14), (17, 23)], "amount": (10, 40),  "cadence": (0, 2), "fee_usd": 1.99},
    "Grubhub":       {"hours": [(11, 14), (17, 23)], "amount": (10, 40),  "cadence": (0, 2), "fee_usd": 0.0},
    "Instacart":     {"hours": [(9, 20)],            "amount": (20, 80),  "cadence": (0, 3), "fee_usd": 0.0},
    "Shipt":         {"hours": [(9, 20)],            "amount": (20, 75),  "cadence": (0, 3), "fee_usd": 0.0},
    "TaskRabbit":    {"hours": [(9, 18)],            "amount": (40, 300), "cadence": (2, 7), "fee_usd": 0.0},
    "Fiverr (design)": {"hours": [(8, 22)],          "amount": (20, 200), "cadence": (3, 14),"fee_usd": 0.0},
    "Fiverr":        {"hours": [(8, 22)],            "amount": (20, 200), "cadence": (3, 14),"fee_usd": 0.0},
    "Amazon Flex":   {"hours": [(5, 10)],            "amount": (70, 150), "cadence": (1, 3), "fee_usd": 0.0},
    "Walmart Spark": {"hours": [(9, 21)],            "amount": (15, 50),  "cadence": (0, 2), "fee_usd": 0.0},
    "Postmates":     {"hours": [(11, 23)],           "amount": (12, 40),  "cadence": (0, 3), "fee_usd": 0.0},
    "Rover":         {"hours": [(7, 21)],            "amount": (25, 80),  "cadence": (1, 7), "fee_usd": 0.0},
    "Care.com":      {"hours": [(7, 21)],            "amount": (50, 200), "cadence": (3, 14),"fee_usd": 0.0},
    "occasional Grubhub": {"hours": [(11, 14), (17, 23)], "amount": (10, 40), "cadence": (0, 2), "fee_usd": 0.0},
    "occasional Uber": {"hours": [(6, 11), (16, 23)], "amount": (8, 50),  "cadence": (0, 2), "fee_usd": 0.0},
}

# ── Archetype defaults (used when a field isn't in the persona) ─────────────

DEFAULT_FRAUD_VECTORS = {
    "remittance": ["phone_scam", "romance_scam", "wire_transfer", "fake_ICE_call",
                   "tech_support_scam", "whatsapp_impersonation"],
    "gig_worker": ["ato", "bec", "synthetic_id", "credential_stuffing", "account_takeover"],
    "unbanked":   ["check_fraud", "prepaid_card", "phone_scam", "kiosk_fraud", "counterfeit_check"],
    "itin":       ["tax_refund_fraud", "identity_theft", "synthetic_id", "phone_scam",
                   "irs_impersonation"],
}

DEFAULT_HOUR_RANGES = {
    "remittance": [(10, 14), (17, 22)],
    "gig_worker": [(7, 22)],
    "unbanked":   [(9, 19)],
    "itin":       [(9, 18)],
}

DEFAULT_CADENCE_DAYS = {"remittance": 14, "gig_worker": 2, "unbanked": 7, "itin": 7}

DEFAULT_PEAK_DAYS = {"remittance": [4, 5], "gig_worker": [4, 5, 6], "unbanked": [4], "itin": [0, 1]}

# ── Family-crisis-history parser → per-persona fraud-vector weights ─────────

FRAUD_EVENT_PATTERNS = [
    (r"phone_scam",              "phone_scam"),
    (r"irs[_ ]impersonat",       "irs_impersonation"),
    (r"fake_ice_call",           "fake_ICE_call"),
    (r"tech[_ ]support[_ ]scam", "tech_support_scam"),
    (r"romance[_ ]scam",         "romance_scam"),
    (r"whatsapp[_ ]impersonat",  "whatsapp_impersonation"),
    (r"grandparent[_ ]scam",     "grandparent_scam"),
    (r"courier[_ ]theft",        "courier_theft"),
    (r"wage[_ ]theft",           "wage_theft"),
    (r"credential[_ ]stuffing",  "credential_stuffing"),
    (r"account[_ ]takeover|\bato\b", "ato"),
    (r"sim[_ ]swap",             "sim_swap"),
    (r"synthetic[_ ]id|synthetic[_ ]identity", "synthetic_id"),
    (r"\bbec\b|business[_ ]email", "bec"),
    (r"tax[_ ]refund[_ ]fraud|intercepted[_ ]refund", "tax_refund_fraud"),
    (r"identity[_ ]theft",       "identity_theft"),
    (r"earthquake[_ ]aid|disaster[_ ]relief", "earthquake_aid_scam"),
    (r"boi[_ ]scam|cta",         "funnel_account"),  # BOI-form scam maps to funnel-account advisory, close enough
    (r"check[_ ]fraud|counterfeit[_ ]check", "check_fraud"),
    (r"ivts|hawala|informal[_ ]courier|informal[_ ]merchant", "ivts"),
    (r"funnel[_ ]account|structured[_ ]deposit", "funnel_account"),
    (r"hurricane[_ ]|disaster[_ ]aid|fake[_ ]charity|relief[_ ]scam", "disaster_relief_scam"),
    (r"phishing|cyber[_ ]incident", "phishing"),
    (r"money[_ ]mule", "money_mule"),
    (r"lax[_ ]kyc|kyc[_ ]circumvention", "lax_kyc"),
    (r"unlicensed[_ ]msb", "unlicensed_msb"),
    (r"false[_ ]chargeback|false[_ ]claim", "false_chargeback"),
    (r"covid[_ ]stimulus|covid[_ ]imposter|fake[_ ]government|stimulus[_ ]impersonation", "fake_government_official"),
    (r"unauthorized[_ ]ach|payment[_ ]processor[_ ]fraud", "unauthorized_ach"),
    (r"tps[_ ]termination",      ""),  # NOT a fraud vector — ambient anxiety only; empty string to skip
    (r"hospital|medical|meds_recurring", ""),  # medical crisis, not fraud
    (r"school[_ ]fees|university[_ ]fees|tuition", ""),  # family obligation, not fraud
]


def extract_persona_fraud_vectors(persona: dict, archetype: str) -> tuple[list[str], np.ndarray]:
    """Return (vectors, weights) giving per-persona fraud-vector preference.

    Vectors documented in family_crisis_history get weight 2.0; archetype
    defaults get weight 1.0. Duplicates collapsed.
    """
    docs: list[str] = []
    for event in persona.get("family_crisis_history", []) or []:
        if not isinstance(event, str):
            continue
        ev = event.lower()
        for pattern, vector in FRAUD_EVENT_PATTERNS:
            if re.search(pattern, ev):
                if vector and vector not in docs:
                    docs.append(vector)
                break
    defaults = [v for v in DEFAULT_FRAUD_VECTORS[archetype] if v not in docs]
    vectors = docs + defaults
    weights = np.array([2.0] * len(docs) + [1.0] * len(defaults))
    weights = weights / weights.sum()
    return vectors, weights

# ── Parameter extraction (no Adaption schema needed) ────────────────────────

def extract_params_v3(persona: dict, archetype: str) -> dict:
    # Amount band — use persona's loss_tolerance_usd to set a ceiling
    tol = persona.get("loss_tolerance_usd") or 500
    arch_default_bands = {
        "remittance": (50, 2500),
        "gig_worker": (5, 300),
        "unbanked":   (20, 1500),
        "itin":       (100, 5000),
    }
    lo, hi = arch_default_bands[archetype]
    amount_bands = [(float(lo), float(hi))]

    # Channels — from persona's primary/secondary or platform_mix
    channels: list[str] = []
    if archetype == "remittance":
        tsl = persona.get("transfer_service_loyalty") or {}
        for k in ("primary", "secondary"):
            v = tsl.get(k)
            if isinstance(v, str) and v and v != "none":
                channels.append(v)
    elif archetype == "gig_worker":
        channels = list((persona.get("platform_mix") or {}).keys())
    elif archetype == "unbanked":
        for p in persona.get("prepaid_card_stack") or []:
            channels.append(p)
        channels.extend(["nonbank money order", "check casher"])
    elif archetype == "itin":
        channels = [persona.get("business_type", "Schedule C")]
    if not channels:
        channels = ["unknown"]

    # Platform schedules — for gig workers only, built from platform_mix + PLATFORM_DB
    platform_schedules: dict[str, dict] = {}
    if archetype == "gig_worker":
        pm = persona.get("platform_mix") or {}
        for plat, weight in pm.items():
            ref = PLATFORM_DB.get(plat, PLATFORM_DB.get("Uber"))
            platform_schedules[plat] = {
                "weight": float(weight),
                "hours":  ref["hours"],
                "amount": ref["amount"],
                "cadence": ref["cadence"],
                "fee_usd": ref["fee_usd"],
            }

    # Hours / cadence fallbacks (independent path)
    hour_ranges = DEFAULT_HOUR_RANGES[archetype]
    default_cad = DEFAULT_CADENCE_DAYS[archetype]
    sub_cadences = [{"days_between": (max(1, default_cad - 3), default_cad + 3), "weight": 1.0}]

    # Peak days
    peak_days = DEFAULT_PEAK_DAYS[archetype]

    # Quarterly seasonality
    quarterly = {"Q1": 0.95, "Q2": 1.0, "Q3": 1.0, "Q4": 1.1}

    # Device defaults
    device_type = persona.get("device", "Android")
    device_stability = persona.get("device_stability", 0.75)

    return {
        "amount_bands": amount_bands,
        "channels": channels,
        "hour_ranges": hour_ranges,
        "peak_days": peak_days,
        "sub_cadences": sub_cadences,
        "platform_schedules": platform_schedules,
        "quarterly": quarterly,
        "languages": persona.get("language_mix") or ["en"],
        "loss_tolerance_usd": float(persona.get("loss_tolerance_usd") or 500),
        "age": int(persona.get("age") or 35),
        "device_type": device_type,
        "device_stability": device_stability,
    }

# ── Per-persona sampler (ported from v2 with v3 additions) ──────────────────

def sample_persona(persona: dict, n: int, archetype: str, rng: np.random.Generator) -> pd.DataFrame:
    params = extract_params_v3(persona, archetype)
    vectors, fv_weights = extract_persona_fraud_vectors(persona, archetype)

    fraud_rate = 0.10
    is_fraud = rng.choice([0, 1], size=n, p=[1 - fraud_rate, fraud_rate])
    fraud_mask = is_fraud == 1

    # Amounts: lognormal within band, loss-tolerance-capped for legit, amplified for fraud
    lo, hi = params["amount_bands"][0]
    mu = np.log(max((lo + hi) / 2.0, 1.0))
    amounts = rng.lognormal(mean=mu, sigma=0.35, size=n)
    amounts = np.clip(amounts, lo * 0.7, hi * 1.5)
    loss_tol = params["loss_tolerance_usd"]
    legit_mask = ~fraud_mask
    amounts[legit_mask] = np.minimum(amounts[legit_mask], loss_tol * 1.1)
    amounts[fraud_mask] = amounts[fraud_mask] * rng.uniform(1.5, 3.5, size=fraud_mask.sum())

    # Joint path for gig workers, independent path otherwise
    plat_scheds = params["platform_schedules"]
    if plat_scheds:
        plat_names = list(plat_scheds.keys())
        plat_weights = np.array([plat_scheds[p]["weight"] for p in plat_names])
        plat_weights = plat_weights / plat_weights.sum()
        plat_idx = rng.choice(len(plat_names), size=n, p=plat_weights)
        channels = np.array([plat_names[pi] for pi in plat_idx])

        hours = np.zeros(n, dtype=int)
        days_since = np.zeros(n, dtype=int)
        fees = np.zeros(n)
        for i in range(n):
            ps = plat_scheds[plat_names[plat_idx[i]]]
            # hour from platform's time window
            hr_choice = rng.choice(len(ps["hours"]))
            h_s, h_e = ps["hours"][hr_choice]
            hours[i] = rng.integers(h_s, max(h_s + 1, h_e) + 1)
            # amount from platform band (override)
            a_lo, a_hi = ps["amount"]
            amt = rng.lognormal(np.log(max((a_lo + a_hi) / 2, 1)), 0.18)
            amounts[i] = np.clip(amt, a_lo * 0.8, a_hi * 1.3)
            if fraud_mask[i]:
                amounts[i] *= rng.uniform(1.5, 3.5)
            # cadence from platform
            c_lo, c_hi = ps["cadence"]
            days_since[i] = rng.integers(c_lo, c_hi + 1)
            # fee from platform
            base_fee = ps["fee_usd"]
            if base_fee > 0:
                fees[i] = max(0.5, base_fee + rng.normal(0, 0.10))
            else:
                fees[i] = 0.0

        # tight hour jitter for joint path
        jitter = rng.normal(0, 0.3, size=n).astype(int)
        hours = np.clip(hours + jitter, 0, 23).astype(int)
        fraud_hour_shift = rng.integers(-3, 4, size=fraud_mask.sum())
        hours[fraud_mask] = np.clip(hours[fraud_mask] + fraud_hour_shift, 0, 23)
    else:
        # independent path (non-gig archetypes)
        hr_ranges = params["hour_ranges"]
        range_idx = rng.integers(0, len(hr_ranges), size=n)
        hours = np.array([
            rng.integers(hr_ranges[ri][0], max(hr_ranges[ri][0] + 1, hr_ranges[ri][1]) + 1)
            for ri in range_idx
        ])
        jitter = rng.normal(0, 0.5, size=n).astype(int)
        hours = np.clip(hours + jitter, 0, 23).astype(int)
        fraud_hour_shift = rng.integers(-4, 5, size=fraud_mask.sum())
        hours[fraud_mask] = np.clip(hours[fraud_mask] + fraud_hour_shift, 0, 23)

        sub_cads = params["sub_cadences"]
        cad_weights = np.array([sc["weight"] for sc in sub_cads])
        cad_weights = cad_weights / cad_weights.sum()
        cad_idx = rng.choice(len(sub_cads), size=n, p=cad_weights)
        days_since = np.array([
            rng.integers(sub_cads[ci]["days_between"][0], sub_cads[ci]["days_between"][1] + 1)
            for ci in cad_idx
        ])
        channels = rng.choice(params["channels"], size=n)

        # Realistic fees — archetype defaults
        if archetype in ("remittance", "unbanked"):
            fees = amounts * rng.uniform(0.02, 0.05, size=n)
        else:
            fees = np.where(
                amounts < 500,
                rng.uniform(1.49, 2.99, size=n),
                amounts * rng.uniform(0.005, 0.02, size=n),
            )

    # Day-of-week weighted toward peak days
    dow_weights = np.ones(7) * 0.02
    for d in params["peak_days"]:
        dow_weights[d] = 0.4
    dow_weights = dow_weights / dow_weights.sum()
    dow = rng.choice(7, size=n, p=dow_weights)

    # Languages
    languages = rng.choice(params["languages"], size=n)

    # Timestamps
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    days_back = rng.integers(0, 365, size=n)
    timestamps = [
        (now - timedelta(days=int(days_back[i]))).replace(
            hour=int(hours[i]), minute=int(rng.integers(0, 60)), second=0
        ).isoformat()
        for i in range(n)
    ]

    # Quarterly seasonality on amounts
    quarters = [((now - timedelta(days=int(d))).month - 1) // 3 + 1 for d in days_back]
    q_mods = np.array([params["quarterly"].get(f"Q{q}", 1.0) for q in quarters])
    amounts = amounts * q_mods

    # Ages: small jitter around persona age
    ages = np.clip(rng.normal(params["age"], 2, size=n), 18, 85).astype(int)

    # Account age derived from sender_tenure_years or credit_file_age_years
    tenure_years = persona.get("sender_tenure_years") or persona.get("credit_file_age_years") or 3
    tenure_mean_days = max(30, int(tenure_years * 365))
    account_age = np.clip(
        rng.normal(tenure_mean_days, tenure_mean_days * 0.15, size=n),
        30, tenure_mean_days * 1.3 + 30
    ).astype(int)

    # txn_count_30d via Poisson on cadence
    avg_cadence = float(np.mean(days_since)) if len(days_since) else 7.0
    expected_30d = max(1, int(30.0 / max(avg_cadence, 0.5)))
    txn_count_30d = np.clip(
        rng.poisson(expected_30d, size=n), 1, expected_30d * 3 + 1
    ).astype(int)

    # Fraud vector: per-persona weighted selection for fraud, instrument label for legit
    fv_sampled = rng.choice(vectors, size=n, p=fv_weights)
    fv = np.where(fraud_mask, fv_sampled, channels)

    typology_refs = [resolve_typology(vec, f) for vec, f in zip(fv, is_fraud)]

    df = pd.DataFrame({
        "data_uuid": [str(uuid.uuid4()) for _ in range(n)],
        "id": [f"v4_{archetype}_{uuid.uuid4().hex[:10]}" for _ in range(n)],
        "archetype": archetype,
        "source": "tabddpm_v4_persona_grounded",
        "persona_id": persona["persona_id"],
        "dataset_version": "v4",
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
        # v3 additions
        "persona_source_ids": [persona.get("persona_source_ids", [])] * n,
        "behavioral_evidence_grade": persona.get("behavioral_evidence_grade", "D"),
        "fraud_vector_typology_ref": typology_refs,
    })
    return df

# ── Orchestrator ─────────────────────────────────────────────────────────────

def generate_archetype(archetype: str, samples: int, rng: np.random.Generator) -> pd.DataFrame:
    doc = json.loads((V4 / archetype / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))
    personas = doc["personas"]
    base = samples // len(personas)
    rem = samples - base * len(personas)
    alloc = [base] * len(personas)
    for i in range(rem):
        alloc[i] += 1

    frames = []
    for persona, n in zip(personas, alloc):
        frames.append(sample_persona(persona, n, archetype, rng))
    df = pd.concat(frames, ignore_index=True)
    return df.sample(frac=1.0, random_state=42).reset_index(drop=True)


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
    rng = np.random.default_rng(args.seed)

    for arch in targets:
        df = generate_archetype(arch, args.samples_per_archetype, rng)
        out_dir = V4 / arch / "synthetic"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "transactions.parquet"
        df.to_parquet(out, index=False)
        typology_fill = df["fraud_vector_typology_ref"].notna().mean()
        g = df["behavioral_evidence_grade"].value_counts().to_dict()
        print(f"[{arch}] {len(df)} rows  fraud_rate={df['is_fraud'].mean():.3f}  "
              f"typology_non_null={typology_fill:.3f}  "
              f"grade_pct={ {k: round(100*v/len(df),1) for k,v in g.items()} }")
        if arch == "gig_worker":
            # sanity: Amazon Flex should be concentrated 5-9am
            flex = df[df["instrument"] == "Amazon Flex"]
            if len(flex):
                print(f"  Amazon Flex hour mean={flex['hour_of_day'].mean():.1f} (target ~7)")
        print(f"  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
