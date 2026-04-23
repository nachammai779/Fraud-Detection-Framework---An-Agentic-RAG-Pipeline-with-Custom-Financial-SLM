"""
One-shot persona edit script — applies the three typology-gap-closure edits:

  1. Gig workers: add ATO / BEC / SIM-swap events to 3 personas (gig_001, gig_006, gig_012)
     + backfill fraud events to 3 personas whose summaries already describe them
     but whose family_crisis_history was empty (gig_004, gig_009, gig_011)
  2. Remittance: add IVTS / hawala / funnel-account events to 3 personas
     (rem_004, rem_009, rem_012)
  3. Disaster-relief: add disaster-fraud exposure to 2 personas with disaster-tied
     ancestry (rem_002 Honduran hurricane, rem_011 PR Maria)

Writes back to persona_profiles.json in place. Idempotent: checks whether the
event keyword is already present before appending.

Run once:
  python src/personas_v3/_apply_persona_edits.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "datasets_v3"


# ── edits table: (persona_id, archetype, new event, grounding_key, grounding_entry) ──

GIG_EDITS = [
    # New events (user-requested)
    (
        "gig_001", "gig_worker",
        "sim_swap_account_takeover_attempted_2024",
        "fraud_exposure_sim_swap_ato",
        {
            "value": "SIM-swap attack targeting platform-account 2FA, attempted 2024, detected",
            "evidence_basis": "FTA_IDENTITY_2024_T6 Account Takeover + SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD (FIN-2011-A016); SIM-swap is a documented attack vector against gig workers with platform-locked payouts",
            "confidence": "INFERRED",
            "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
        },
        ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
    ),
    (
        "gig_006", "gig_worker",
        "bec_salon_supplier_invoice_fraud_2024_detected",
        "fraud_exposure_bec_supplier_invoice",
        {
            "value": "Fake supplier-invoice email requesting wire change, detected 2024",
            "evidence_basis": "FTA_IDENTITY_2024_T11 Business Email Compromise + SAR_ADVISORY_BEC_FRAUD (FIN-2019-A005); BEC targeting small-business owners (nail salons) is documented in FinCEN advisories",
            "confidence": "INFERRED",
            "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
        },
        ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
        "upgrade_grade_to_B",
    ),
    (
        "gig_012", "gig_worker",
        "phishing_taskrabbit_credential_compromise_2024_detected",
        "fraud_exposure_phishing_cyber_incident",
        {
            "value": "Phishing email impersonating TaskRabbit security team, credentials nearly captured, detected 2024",
            "evidence_basis": "FTA_IDENTITY_2024_T9 Cyber Incident + SAR_ADVISORY_CYBER_EVENTS (FIN-2016-A005); platform-worker phishing is common",
            "confidence": "INFERRED",
            "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
        },
        ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
    ),
    # Backfills: structured events for personas whose summaries already describe fraud
    (
        "gig_004", "gig_worker",
        "bec_uber_driver_relations_impersonation_2024_detected",
        "family_crisis_history_backfill",
        {
            "value": "BEC attempt impersonating Uber Driver Relations (already referenced in summary); formalized in family_crisis_history for fraud-vector weighting",
            "evidence_basis": "Already grounded per gig_004 summary + existing grounding fraud_exposure_bec_attempt",
            "confidence": "DIRECT",
            "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
        },
        [],  # sources already present
    ),
    (
        "gig_009", "gig_worker",
        "synthetic_id_platform_account_duplicate_2024_detected",
        "family_crisis_history_backfill",
        {
            "value": "Synthetic-ID attack against DoorDash account (already referenced in summary); formalized in family_crisis_history",
            "evidence_basis": "Already grounded per gig_009 summary + existing grounding fraud_exposure_synthetic_id",
            "confidence": "DIRECT",
            "source_ids": ["fed_reserve_synthetic_identity_fraud", "fincen_2024_identity_fta"],
        },
        [],
    ),
    (
        "gig_011", "gig_worker",
        "account_takeover_credential_stuffing_2024_detected",
        "family_crisis_history_backfill",
        {
            "value": "ATO via credential stuffing (already referenced in summary); formalized in family_crisis_history",
            "evidence_basis": "Already grounded per gig_011 summary + existing grounding fraud_exposure_ato_credential_stuffing",
            "confidence": "DIRECT",
            "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
        },
        [],
    ),
]

REMITTANCE_EDITS = [
    # IVTS / circumvention class
    (
        "rem_004", "remittance",
        "family_requested_hawala_routing_2023_declined",
        "fraud_exposure_ivts_hawala_pressure",
        {
            "value": "Family in Lagos requested hawala-style informal transfer to bypass fees; declined by Oluwaseun as tech-worker wary of unregulated channels",
            "evidence_basis": "SAR_ADVISORY_IVTS (FIN-2010-A011); Nigeria-US hawala channels documented in FinCEN IVTS advisory",
            "confidence": "INFERRED",
            "source_ids": ["fincen_sar_key_terms"],
        },
        ["fincen_sar_key_terms"],
    ),
    (
        "rem_009", "remittance",
        "ivts_ghanaian_merchant_network_recurring",
        "fraud_exposure_ivts_ghanaian_merchant",
        {
            "value": "Ongoing partial usage of Bronx Ghanaian-merchant informal value transfer system (already in summary); formalized as IVTS event",
            "evidence_basis": "SAR_ADVISORY_IVTS (FIN-2010-A011) — informal value transfer systems used by diaspora communities",
            "confidence": "DIRECT",
            "source_ids": ["fincen_sar_key_terms"],
        },
        [],  # already has fincen_sar_key_terms
    ),
    (
        "rem_012", "remittance",
        "funnel_account_routing_observed_2024_avoided",
        "fraud_exposure_funnel_account_sanction_routing",
        {
            "value": "Observed funnel-account-style intermediary routing suggestion for sanctions-affected Russia transfer; avoided",
            "evidence_basis": "SAR_ADVISORY_FUNNEL_ACCOUNT (FIN-2014-A005) — structured deposits routed through single account",
            "confidence": "INFERRED",
            "source_ids": ["fincen_sar_key_terms"],
        },
        ["fincen_sar_key_terms"],
        "upgrade_grade_to_B",
    ),
    # Disaster-relief
    (
        "rem_002", "remittance",
        "hurricane_eta_relief_scam_attempted_2021",
        "fraud_exposure_hurricane_relief_scam",
        {
            "value": "Fake relief charity soliciting wire transfers after Hurricane Eta (Honduras 2020); attempted, detected, not sent",
            "evidence_basis": "SAR_ADVISORY_DISASTER_RELATED_FRAUD (FIN-2017-A007); disaster-relief scams target diaspora communities with recent home-country disasters",
            "confidence": "INFERRED",
            "source_ids": ["fincen_sar_key_terms"],
        },
        ["fincen_sar_key_terms"],
    ),
    (
        "rem_011", "remittance",
        "hurricane_maria_fake_charity_scam_attempted_2018",
        "fraud_exposure_hurricane_maria_relief_scam",
        {
            "value": "Fake Hurricane Maria relief-charity solicitation targeting Puerto Rican diaspora; attempted 2018, detected",
            "evidence_basis": "SAR_ADVISORY_DISASTER_RELATED_FRAUD (FIN-2017-A007); Maria relief-fraud widely documented post-2017 hurricane season",
            "confidence": "INFERRED",
            "source_ids": ["fincen_sar_key_terms"],
        },
        [],  # already has fincen_sar_key_terms
    ),
]


def _apply_edits(archetype: str, edits: list[tuple]) -> int:
    path = V3 / archetype / "personas" / "persona_profiles.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    applied = 0
    for edit in edits:
        persona_id, arch_from_edit, event, grounding_key, grounding_entry, source_ids_add, *rest = edit + ([],)
        if not isinstance(source_ids_add, list):
            # tuple shape with the optional upgrade directive at that slot
            rest = [source_ids_add]
            source_ids_add = []
        upgrade_grade = rest[0] if rest else None

        persona = next((p for p in doc["personas"] if p["persona_id"] == persona_id), None)
        if not persona:
            print(f"  WARN: {persona_id} not found in {archetype}")
            continue

        # family_crisis_history append (idempotent)
        fch = persona.setdefault("family_crisis_history", []) or []
        if event not in fch:
            fch.append(event)
            persona["family_crisis_history"] = fch

        # grounding entry
        persona.setdefault("grounding", {})[grounding_key] = grounding_entry

        # source_ids union
        psids = persona.setdefault("persona_source_ids", []) or []
        for sid in source_ids_add:
            if sid not in psids:
                psids.append(sid)
        persona["persona_source_ids"] = psids

        # grade upgrade
        if upgrade_grade == "upgrade_grade_to_B":
            persona["behavioral_evidence_grade"] = "B"

        applied += 1
        print(f"  {persona_id}: +{event}  (grade={persona['behavioral_evidence_grade']})")

    # Refresh synthesis_notes.grade_distribution_achieved counts
    from collections import Counter
    grades = Counter(p["behavioral_evidence_grade"] for p in doc["personas"])
    doc["synthesis_notes"]["grade_distribution_achieved"] = dict(sorted(grades.items()))

    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return applied


def _patch_generator_patterns():
    """Extend FRAUD_EVENT_PATTERNS in tabddpm_v3_generator.py with new keywords."""
    gen_path = ROOT / "src" / "personas_v3" / "tabddpm_v3_generator.py"
    text = gen_path.read_text(encoding="utf-8")
    marker = '(r"check[_ ]fraud|counterfeit[_ ]check", "check_fraud"),'
    additions = '''(r"check[_ ]fraud|counterfeit[_ ]check", "check_fraud"),
    (r"ivts|hawala|informal[_ ]courier|informal[_ ]merchant", "ivts"),
    (r"funnel[_ ]account|structured[_ ]deposit", "funnel_account"),
    (r"hurricane[_ ]|disaster[_ ]aid|fake[_ ]charity|relief[_ ]scam", "disaster_relief_scam"),
    (r"phishing|cyber[_ ]incident", "phishing"),'''
    if "ivts|hawala" in text:
        print("  generator patterns already patched, skipping")
        return False
    text = text.replace(marker, additions)
    gen_path.write_text(text, encoding="utf-8")
    print(f"  patched {gen_path.name} with 4 new fraud-event patterns")
    return True


def main():
    print("Applying gig_worker edits (6 personas)...")
    n1 = _apply_edits("gig_worker", GIG_EDITS)

    print("\nApplying remittance edits (5 personas)...")
    n2 = _apply_edits("remittance", REMITTANCE_EDITS)

    print("\nPatching generator fraud-event patterns...")
    _patch_generator_patterns()

    print(f"\nTotal persona edits applied: {n1 + n2}")


if __name__ == "__main__":
    main()
