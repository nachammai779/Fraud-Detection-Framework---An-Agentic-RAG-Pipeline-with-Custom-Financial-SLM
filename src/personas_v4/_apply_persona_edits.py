"""
V4 persona edit script — applies typology-gap-closure edits on datasets_v4/.

Three groups:
  Group 1 — inherited from v3 draft (11 edits): ATO/BEC/SIM-swap for gig,
    IVTS/hawala/funnel for remittance, disaster-relief for 2 personas.
  Group 2 — v4-new (5 edits): hit five more unexercised typology codes
    (T4 3PML, T5 Circumventing Standards, T12 False Claims,
     SAR_COVID19_IMPOSTER_SCAMS, SAR_THIRD_PARTY_PAYMENT_PROCESSORS).

Idempotent — checks if event already present before appending.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"


def _edit(persona_id, archetype, event, grounding_key, grounding_entry,
          source_ids_add=None, upgrade_to=None):
    return {
        "persona_id": persona_id, "archetype": archetype, "event": event,
        "grounding_key": grounding_key, "grounding_entry": grounding_entry,
        "source_ids_add": source_ids_add or [], "upgrade_to": upgrade_to,
    }


# ── Group 1: original 11 edits (v3-era, now applied to v4) ───────────────────

GROUP1 = [
    # gig — new events
    _edit("gig_001", "gig_worker", "sim_swap_account_takeover_attempted_2024",
          "fraud_exposure_sim_swap_ato",
          {"value": "SIM-swap attack targeting platform-account 2FA, detected 2024",
           "evidence_basis": "SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD (FIN-2011-A016); SIM-swap attack vector on gig-worker platform accounts",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"]},
          ["fincen_sar_key_terms", "fincen_2024_identity_fta"]),

    _edit("gig_006", "gig_worker", "bec_salon_supplier_invoice_fraud_2024_detected",
          "fraud_exposure_bec_supplier_invoice",
          {"value": "Fake supplier-invoice email requesting wire change, detected 2024",
           "evidence_basis": "SAR_ADVISORY_BEC_FRAUD (FIN-2019-A005); BEC targets small-business owners",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"]},
          ["fincen_sar_key_terms", "fincen_2024_identity_fta"], upgrade_to="B"),

    _edit("gig_012", "gig_worker", "phishing_taskrabbit_credential_compromise_2024_detected",
          "fraud_exposure_phishing_cyber_incident",
          {"value": "Phishing impersonating TaskRabbit security team, credentials nearly captured, 2024",
           "evidence_basis": "SAR_ADVISORY_CYBER_EVENTS (FIN-2016-A005)",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"]},
          ["fincen_sar_key_terms", "fincen_2024_identity_fta"]),

    # gig — backfills for events already in persona summaries
    _edit("gig_004", "gig_worker", "bec_uber_driver_relations_impersonation_2024_detected",
          "family_crisis_history_backfill",
          {"value": "BEC impersonation already in summary; formalized in family_crisis_history",
           "evidence_basis": "Already grounded per gig_004 summary",
           "confidence": "DIRECT", "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"]},
          []),

    _edit("gig_009", "gig_worker", "synthetic_id_platform_account_duplicate_2024_detected",
          "family_crisis_history_backfill",
          {"value": "Synthetic-ID attack already in summary; formalized",
           "evidence_basis": "Already grounded",
           "confidence": "DIRECT", "source_ids": ["fed_reserve_synthetic_identity_fraud", "fincen_2024_identity_fta"]},
          []),

    _edit("gig_011", "gig_worker", "account_takeover_credential_stuffing_2024_detected",
          "family_crisis_history_backfill",
          {"value": "ATO via credential stuffing already in summary; formalized",
           "evidence_basis": "Already grounded",
           "confidence": "DIRECT", "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"]},
          []),

    # remittance — IVTS / funnel / hawala
    _edit("rem_004", "remittance", "family_requested_hawala_routing_2023_declined",
          "fraud_exposure_ivts_hawala_pressure",
          {"value": "Family in Lagos requested hawala-style transfer; declined",
           "evidence_basis": "SAR_ADVISORY_IVTS (FIN-2010-A011)",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms"]},
          ["fincen_sar_key_terms"]),

    _edit("rem_009", "remittance", "ivts_ghanaian_merchant_network_recurring",
          "fraud_exposure_ivts_ghanaian_merchant",
          {"value": "Ongoing partial use of Bronx Ghanaian-merchant IVTS",
           "evidence_basis": "SAR_ADVISORY_IVTS (FIN-2010-A011)",
           "confidence": "DIRECT", "source_ids": ["fincen_sar_key_terms"]},
          []),

    _edit("rem_012", "remittance", "funnel_account_routing_observed_2024_avoided",
          "fraud_exposure_funnel_account_sanction_routing",
          {"value": "Observed funnel-account routing suggestion for Russia transfer; avoided",
           "evidence_basis": "SAR_ADVISORY_FUNNEL_ACCOUNT (FIN-2014-A005)",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms"]},
          ["fincen_sar_key_terms"], upgrade_to="B"),

    # remittance — disaster-relief
    _edit("rem_002", "remittance", "hurricane_eta_relief_scam_attempted_2021",
          "fraud_exposure_hurricane_relief_scam",
          {"value": "Fake Hurricane Eta relief charity soliciting wire transfers (Honduras 2020); attempted, detected",
           "evidence_basis": "SAR_ADVISORY_DISASTER_RELATED_FRAUD (FIN-2017-A007)",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms"]},
          ["fincen_sar_key_terms"]),

    _edit("rem_011", "remittance", "hurricane_maria_fake_charity_scam_attempted_2018",
          "fraud_exposure_hurricane_maria_relief_scam",
          {"value": "Fake Hurricane Maria relief-charity solicitation; attempted 2018, detected",
           "evidence_basis": "SAR_ADVISORY_DISASTER_RELATED_FRAUD (FIN-2017-A007)",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms"]},
          []),
]


# ── Group 2: v4-new 5 edits (typology-coverage expansion) ────────────────────

GROUP2 = [
    # T4 Third-Party Money Laundering — via money-mule recruitment
    _edit("rem_010", "remittance", "money_mule_recruitment_approach_dominican_2024_declined",
          "fraud_exposure_money_mule_recruitment",
          {"value": "Approached by a stranger on Facebook to 'help move funds' in exchange for a fee; declined after recognising typical mule recruitment pattern",
           "evidence_basis": "SAR_ADVISORY_COVID19_IMPOSTER_SCAMS (FIN-2020-A003) documents money-mule recruitment targeting diaspora communities",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"]},
          ["fincen_sar_key_terms", "fincen_2024_identity_fta"], upgrade_to="B"),

    # T5 Circumventing Standards — via unlicensed MSB observation
    _edit("unb_009", "unbanked", "unlicensed_msb_bodega_observed_2024",
          "fraud_exposure_unlicensed_msb",
          {"value": "Observed a Detroit bodega offering money-transfer services without visible MSB licensing; declined to use",
           "evidence_basis": "FTA_IDENTITY_2024_T5 Circumventing Standards; unlicensed MSB activity documented by FinCEN",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"]},
          ["fincen_sar_key_terms", "fincen_2024_identity_fta"]),

    # T12 False Claims — via false-chargeback from Rover client
    _edit("gig_008", "gig_worker", "false_chargeback_rover_client_2024_disputed",
          "fraud_exposure_false_chargeback",
          {"value": "A Rover dog-walking client filed a false chargeback claiming service not rendered; disputed with platform, eventually refunded from platform reserve",
           "evidence_basis": "FTA_IDENTITY_2024_T12 False Claims; chargeback fraud is documented as a platform-worker risk",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"]},
          ["fincen_sar_key_terms", "fincen_2024_identity_fta"], upgrade_to="B"),

    # SAR COVID imposter scams — historical stimulus-impersonation targeting
    _edit("rem_007", "remittance", "covid_stimulus_impersonation_scam_attempted_2021",
          "fraud_exposure_covid_imposter_stimulus",
          {"value": "Received calls in 2021 from caller impersonating a federal 'COVID-19 Economic Impact Payment' representative demanding bank details; detected, not lost",
           "evidence_basis": "SAR_ADVISORY_COVID19_IMPOSTER_SCAMS (FIN-2020-A003); fake_government_official vector documented in FinCEN advisory",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms"]},
          ["fincen_sar_key_terms"]),

    # SAR Third-Party Payment Processors — unauthorized ACH via prepaid card
    _edit("unb_003", "unbanked", "unauthorized_ach_greendot_prepaid_2024_reversed",
          "fraud_exposure_unauthorized_ach_via_processor",
          {"value": "Unauthorized ACH debit from Green Dot prepaid card via a third-party payment processor; caught at month-end reconciliation, reversed with help from prepaid provider",
           "evidence_basis": "SAR_ADVISORY_THIRD_PARTY_PAYMENT_PROCESSORS (FIN-2012-A010); processor-facilitated unauthorised ACH is a documented consumer-fraud pattern",
           "confidence": "INFERRED", "source_ids": ["fincen_sar_key_terms"]},
          ["fincen_sar_key_terms"]),
]


def _apply(edits):
    by_archetype: dict[str, list] = {}
    for e in edits:
        by_archetype.setdefault(e["archetype"], []).append(e)

    applied = 0
    for arch, ed_list in by_archetype.items():
        path = V4 / arch / "personas" / "persona_profiles.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        for e in ed_list:
            persona = next((p for p in doc["personas"] if p["persona_id"] == e["persona_id"]), None)
            if not persona:
                print(f"  WARN: {e['persona_id']} not found")
                continue
            fch = persona.setdefault("family_crisis_history", []) or []
            if e["event"] not in fch:
                fch.append(e["event"])
                persona["family_crisis_history"] = fch
            persona.setdefault("grounding", {})[e["grounding_key"]] = e["grounding_entry"]
            psids = persona.setdefault("persona_source_ids", []) or []
            for sid in e["source_ids_add"]:
                if sid not in psids:
                    psids.append(sid)
            persona["persona_source_ids"] = psids
            if e["upgrade_to"]:
                persona["behavioral_evidence_grade"] = e["upgrade_to"]
            print(f"  {e['persona_id']}: +{e['event']}  (grade={persona['behavioral_evidence_grade']})")
            applied += 1

        # Refresh synthesis_notes
        grades = Counter(p["behavioral_evidence_grade"] for p in doc["personas"])
        doc["synthesis_notes"]["grade_distribution_achieved"] = dict(sorted(grades.items()))
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return applied


def _patch_generator_patterns():
    gen = ROOT / "src" / "personas_v4" / "tabddpm_v4_generator.py"
    text = gen.read_text(encoding="utf-8")

    # 1. SAR-preference resolver change
    old_resolver = '''_FRAUD_VECTOR_TO_CODE: dict[str, str] = {}
for code, entry in TYPOLOGY.items():
    if code.startswith("_"):
        continue
    for vec in entry.get("applies_to_fraud_vectors", []):
        _FRAUD_VECTOR_TO_CODE.setdefault(vec.lower(), code)'''
    new_resolver = '''_FRAUD_VECTOR_TO_CODE: dict[str, str] = {}
# SAR advisories first — more specific, citeable advisory codes.
for code, entry in TYPOLOGY.items():
    if code.startswith("SAR_"):
        for vec in entry.get("applies_to_fraud_vectors", []):
            _FRAUD_VECTOR_TO_CODE.setdefault(vec.lower(), code)
for code, entry in TYPOLOGY.items():
    if code.startswith("FTA_"):
        for vec in entry.get("applies_to_fraud_vectors", []):
            _FRAUD_VECTOR_TO_CODE.setdefault(vec.lower(), code)'''
    if "SAR advisories first" not in text:
        text = text.replace(old_resolver, new_resolver)

    # 2. Expanded fraud-event regex patterns
    old_marker = '(r"check[_ ]fraud|counterfeit[_ ]check", "check_fraud"),'
    new_block = '''(r"check[_ ]fraud|counterfeit[_ ]check", "check_fraud"),
    (r"ivts|hawala|informal[_ ]courier|informal[_ ]merchant", "ivts"),
    (r"funnel[_ ]account|structured[_ ]deposit", "funnel_account"),
    (r"hurricane[_ ]|disaster[_ ]aid|fake[_ ]charity|relief[_ ]scam", "disaster_relief_scam"),
    (r"phishing|cyber[_ ]incident", "phishing"),
    (r"money[_ ]mule", "money_mule"),
    (r"unlicensed[_ ]msb|lax[_ ]kyc|kyc[_ ]circumvention", "unlicensed_msb"),
    (r"false[_ ]chargeback|false[_ ]claim", "false_chargeback"),
    (r"covid[_ ]stimulus|covid[_ ]imposter|fake[_ ]government|stimulus[_ ]impersonation", "fake_government_official"),
    (r"unauthorized[_ ]ach|payment[_ ]processor[_ ]fraud", "unauthorized_ach"),'''
    if "money[_ ]mule" not in text:
        text = text.replace(old_marker, new_block)

    gen.write_text(text, encoding="utf-8")
    print("  patched v4 generator: SAR-preference + 9 new fraud patterns")


def main():
    print("Group 1: inherited 11 edits (v3 persona work)...")
    n1 = _apply(GROUP1)

    print("\nGroup 2: v4-new 5 edits (typology coverage expansion)...")
    n2 = _apply(GROUP2)

    print("\nPatching v4 generator (SAR preference + 9 fraud patterns)...")
    _patch_generator_patterns()

    print(f"\nTotal edits applied: {n1 + n2}")


if __name__ == "__main__":
    main()
