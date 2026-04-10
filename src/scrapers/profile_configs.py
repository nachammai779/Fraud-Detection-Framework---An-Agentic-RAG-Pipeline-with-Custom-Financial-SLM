"""
profile_configs.py
==================
Behavioral and demographic profiles for each fraud archetype.
Derived from 1,040 scraped seed narratives across 3 sources.

Used by:
    - src/generators/narrative_generator.py   (multilingual narrative expansion)
    - src/generators/tabddpm_generator.py     (synthetic transaction generation)
    - notebooks/generation/                   (data augmentation pipelines)

Each profile defines:
    - Demographics & geography
    - Transaction behavior patterns
    - Fraud vector distribution (observed from scraped data)
    - Language mix (observed from scraped data)
    - Financial instrument usage
    - Temporal patterns

Usage:
    from profile_configs import PROFILES, get_profile
    remit = get_profile("remittance")
    print(remit["fraud_vectors"])
"""

# ── Remittance ───────────────────────────────────────────────────────────────

REMITTANCE = {
    "archetype": "remittance",
    "description": "Cross-border money transfer fraud targeting immigrant communities",

    # Demographics
    "demographics": {
        "age_range": (25, 65),
        "primary_communities": [
            "Mexican diaspora", "Filipino diaspora", "Nigerian diaspora",
            "Ghanaian diaspora", "Haitian diaspora", "Indian diaspora",
        ],
        "income_bracket": "low-to-middle",
        "banking_status": "banked or semi-banked",
    },

    # Geographic corridors
    "corridors": [
        {"from": "USA", "to": "Mexico", "weight": 0.25},
        {"from": "USA", "to": "Philippines", "weight": 0.15},
        {"from": "USA", "to": "Nigeria", "weight": 0.12},
        {"from": "USA", "to": "Ghana", "weight": 0.10},
        {"from": "USA", "to": "Haiti", "weight": 0.08},
        {"from": "USA", "to": "India", "weight": 0.08},
        {"from": "UK", "to": "Nigeria", "weight": 0.07},
        {"from": "USA", "to": "Guatemala", "weight": 0.05},
        {"from": "USA", "to": "El Salvador", "weight": 0.05},
        {"from": "USA", "to": "Other", "weight": 0.05},
    ],

    # Language distribution (observed from 280 scraped records)
    "language_mix": {
        "en": 0.78,
        "es": 0.06,
        "vi": 0.07,
        "yo": 0.05,
        "hi": 0.02,
        "ht": 0.02,
    },

    # Fraud vectors (observed frequencies, normalized)
    "fraud_vectors": {
        "wire transfer": 0.21,
        "exchange rate": 0.15,
        "emergency": 0.15,
        "interception": 0.08,
        "fake family": 0.07,
        "estafa": 0.06,
        "fraude": 0.06,
        "bonus": 0.05,
        "Western Union": 0.06,
        "MoneyGram": 0.04,
        "unknown": 0.07,
    },

    # Financial instruments
    "instruments": [
        "Western Union", "MoneyGram", "Remitly", "Xoom",
        "Wire transfer (bank)", "Hawala", "Cash pickup",
    ],

    # Transaction patterns for synthetic generation
    "transaction_patterns": {
        "amount_range_usd": (50, 5000),
        "median_amount_usd": 500,
        "frequency": "1-4x per month",
        "peak_days": ["Friday", "Saturday"],
        "peak_hours": (17, 22),
        "typical_fee_pct": (2.0, 8.0),
    },

    # Temporal patterns
    "temporal": {
        "seasonal_peaks": ["December", "March", "May"],
        "event_triggers": [
            "family emergency", "holiday remittance",
            "school fees", "medical bills",
        ],
    },
}

# ── Gig Worker ───────────────────────────────────────────────────────────────

GIG_WORKER = {
    "archetype": "gig_worker",
    "description": "Account takeover and payment fraud targeting gig economy workers",

    "demographics": {
        "age_range": (18, 45),
        "primary_communities": [
            "Rideshare drivers (Uber, Lyft)",
            "Delivery drivers (DoorDash, Instacart)",
            "Freelancers (Fiverr, Upwork)",
            "Indian diaspora tech workers",
            "Tamil diaspora gig workers",
        ],
        "income_bracket": "low-to-middle",
        "banking_status": "banked, app-dependent",
    },

    "corridors": [
        {"region": "US urban metros", "weight": 0.60},
        {"region": "India (UPI/Paytm corridor)", "weight": 0.15},
        {"region": "UK gig economy", "weight": 0.10},
        {"region": "Southeast Asia", "weight": 0.08},
        {"region": "Other", "weight": 0.07},
    ],

    "language_mix": {
        "en": 0.89,
        "hi": 0.06,
        "vi": 0.02,
        "es": 0.02,
        "yo": 0.01,
    },

    "fraud_vectors": {
        "stolen": 0.18,
        "hacked": 0.13,
        "account takeover": 0.11,
        "ATO": 0.11,
        "PayPal": 0.10,
        "Venmo": 0.04,
        "CashApp": 0.04,
        "OTP": 0.04,
        "SIM swap": 0.03,
        "fake support": 0.03,
        "social engineering": 0.03,
        "unknown": 0.16,
    },

    "instruments": [
        "CashApp", "Venmo", "Zelle", "PayPal",
        "Uber instant pay", "DoorDash direct deposit",
        "Bank debit card", "Prepaid card",
    ],

    "transaction_patterns": {
        "amount_range_usd": (5, 3000),
        "median_amount_usd": 150,
        "frequency": "daily to weekly payouts",
        "peak_days": ["Sunday", "Monday"],
        "peak_hours": (20, 2),
        "typical_payout_delay_hours": (0, 72),
    },

    "temporal": {
        "seasonal_peaks": ["January", "June", "November"],
        "event_triggers": [
            "platform policy change", "new driver onboarding",
            "instant pay feature launch", "SIM swap wave",
        ],
    },
}

# ── Unbanked ─────────────────────────────────────────────────────────────────

UNBANKED = {
    "archetype": "unbanked",
    "description": "Prepaid card, payday loan, and kiosk fraud targeting unbanked populations",

    "demographics": {
        "age_range": (20, 60),
        "primary_communities": [
            "Low-income urban populations",
            "Vietnamese diaspora",
            "Somali refugees",
            "Rural underserved communities",
            "Recently arrived immigrants",
        ],
        "income_bracket": "low",
        "banking_status": "unbanked or underbanked",
    },

    "corridors": [
        {"region": "US urban (check cashing corridors)", "weight": 0.45},
        {"region": "US rural (payday loan deserts)", "weight": 0.20},
        {"region": "Vietnamese community hubs", "weight": 0.12},
        {"region": "Somali community hubs", "weight": 0.08},
        {"region": "Latin American immigrant corridors", "weight": 0.10},
        {"region": "Other", "weight": 0.05},
    ],

    "language_mix": {
        "en": 0.84,
        "vi": 0.12,
        "yo": 0.02,
        "es": 0.01,
        "hi": 0.01,
    },

    "fraud_vectors": {
        "predatory": 0.24,
        "prepaid": 0.16,
        "kiosk": 0.12,
        "advance fee": 0.08,
        "fake loan": 0.06,
        "load fee": 0.05,
        "payday loan": 0.04,
        "hawala": 0.03,
        "unknown": 0.22,
    },

    "instruments": [
        "Prepaid Visa/Mastercard", "Green Dot card", "NetSpend",
        "Payday loan", "Check cashing service", "Bill pay kiosk",
        "Money order", "Cash (informal)",
    ],

    "transaction_patterns": {
        "amount_range_usd": (10, 1500),
        "median_amount_usd": 200,
        "frequency": "2-6x per month",
        "peak_days": ["Friday", "Monday"],
        "peak_hours": (9, 18),
        "typical_fee_pct": (3.0, 15.0),
    },

    "temporal": {
        "seasonal_peaks": ["January", "April", "August"],
        "event_triggers": [
            "tax refund season", "utility bill due",
            "rent due cycle", "school fee deadlines",
            "predatory ad campaigns",
        ],
    },
}

# ── ITIN ─────────────────────────────────────────────────────────────────────

ITIN = {
    "archetype": "itin",
    "description": "Identity theft, tax fraud, and synthetic identity targeting ITIN holders",

    "demographics": {
        "age_range": (22, 55),
        "primary_communities": [
            "Undocumented immigrants",
            "ITIN small business owners",
            "Indian H1B/visa holders",
            "Chinese immigrant entrepreneurs",
            "Korean small business owners",
            "Latin American immigrants",
        ],
        "income_bracket": "low-to-middle",
        "banking_status": "mixed — some banked, many underbanked",
    },

    "corridors": [
        {"region": "US (California, Texas, New York, Florida)", "weight": 0.50},
        {"region": "US (Arizona, Illinois, Georgia)", "weight": 0.20},
        {"region": "India (H1B corridor)", "weight": 0.10},
        {"region": "China (EB-5/business corridor)", "weight": 0.08},
        {"region": "Mexico/Central America", "weight": 0.07},
        {"region": "Other", "weight": 0.05},
    ],

    "language_mix": {
        "en": 0.96,
        "vi": 0.02,
        "ta": 0.01,
        "es": 0.01,
    },

    "fraud_vectors": {
        "ITIN": 0.25,
        "EIN": 0.19,
        "identity theft": 0.13,
        "synthetic identity": 0.08,
        "tax return": 0.06,
        "immigration consultant": 0.05,
        "social security": 0.04,
        "mule": 0.03,
        "fake visa": 0.02,
        "unknown": 0.15,
    },

    "instruments": [
        "ITIN tax filing", "EIN business registration",
        "Credit application", "Bank account opening",
        "Mortgage application", "Small business loan",
        "Fake immigration consultancy",
    ],

    "transaction_patterns": {
        "amount_range_usd": (100, 50000),
        "median_amount_usd": 3000,
        "frequency": "seasonal (tax filing) or one-time (identity creation)",
        "peak_days": ["Monday", "Tuesday", "Wednesday"],
        "peak_hours": (9, 17),
        "typical_loss_usd": (500, 25000),
    },

    "temporal": {
        "seasonal_peaks": ["January", "February", "March", "April"],
        "event_triggers": [
            "tax filing season", "ITIN renewal deadline",
            "immigration policy change", "new business formation surge",
            "data breach exposure",
        ],
    },
}

# ── Registry ─────────────────────────────────────────────────────────────────

PROFILES = {
    "remittance": REMITTANCE,
    "gig_worker": GIG_WORKER,
    "unbanked": UNBANKED,
    "itin": ITIN,
}


def get_profile(archetype: str) -> dict:
    """Get profile config for an archetype. Raises KeyError if invalid."""
    if archetype not in PROFILES:
        raise KeyError(
            f"Unknown archetype '{archetype}'. Valid: {list(PROFILES.keys())}"
        )
    return PROFILES[archetype]


def list_archetypes() -> list:
    """Return list of all archetype names."""
    return list(PROFILES.keys())


def get_fraud_vectors(archetype: str) -> dict:
    """Get fraud vector distribution for an archetype."""
    return get_profile(archetype)["fraud_vectors"]


def get_language_mix(archetype: str) -> dict:
    """Get language distribution for an archetype."""
    return get_profile(archetype)["language_mix"]


def get_transaction_params(archetype: str) -> dict:
    """Get transaction generation parameters for an archetype."""
    return get_profile(archetype)["transaction_patterns"]


# ── Summary ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for name, profile in PROFILES.items():
        print(f"\n{'='*60}")
        print(f"{name.upper()}: {profile['description']}")
        print(f"{'='*60}")
        print(f"  Communities:  {', '.join(profile['demographics']['primary_communities'][:3])}...")
        print(f"  Age range:    {profile['demographics']['age_range']}")
        print(f"  Banking:      {profile['demographics']['banking_status']}")
        print(f"  Languages:    {profile['language_mix']}")
        print(f"  Top vectors:  {sorted(profile['fraud_vectors'].items(), key=lambda x: -x[1])[:5]}")
        print(f"  Instruments:  {profile['instruments'][:4]}...")
        tp = profile["transaction_patterns"]
        print(f"  Txn range:    ${tp['amount_range_usd'][0]} - ${tp['amount_range_usd'][1]}")
        print(f"  Txn median:   ${tp['median_amount_usd']}")
        print(f"  Peak months:  {profile['temporal']['seasonal_peaks']}")