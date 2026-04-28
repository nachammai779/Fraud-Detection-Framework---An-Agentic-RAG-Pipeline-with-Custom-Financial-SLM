"""
v4.1 — Add the 3 truly-missing typology codes (FTA_T7, FTA_T8, SAR_HUMAN_TRAFFICKING)
to the v4 dataset.

Approach:
  1. Patch 3 existing personas to add a new fraud-exposure grounding entry +
     a family_crisis_history event, one per missing code.
  2. Synthesize N=100 transaction rows per code by sampling from the host
     persona's existing rows (preserving amount/time/instrument distributions)
     and overriding is_fraud, fraud_vector, and fraud_vector_typology_ref.
  3. Write the 300 synthetic rows to datasets_v4/v4_1/missing_typology_rows.parquet
     with narrative_text empty.
  4. Build datasets_v4/v4_1/missing_typology_for_adaption.jsonl — Adaption-ready
     narrative-fill prompts matching the combined-job format.

After Adaption completes, a follow-up merge step will:
  - Copy narratives into missing_typology_rows.parquet
  - Append the 300 rows to each archetype's transactions_adapted.parquet
  - Rebuild the bundle

Persona picks:
  FTA_T7 Abuse of Access                 -> unb_001 Dorothy Jackson (POA / caregiver abuse)
  FTA_T8 Refusal to Cooperate            -> gig_001 DeShawn Williams (platform refused to produce records for ID-theft dispute)
  SAR_HUMAN_TRAFFICKING                  -> itin_010 Fatou Diallo (wage confiscation in braiding salon)
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"
OUT = V4 / "v4_1"
SEED = 42
PER_CODE = 100


PATCHES = {
    "unbanked": {
        "persona_id": "unb_001",
        "event_tag": "power_of_attorney_abuse_caregiver_2024",
        "grounding_key": "fraud_exposure_power_of_attorney_abuse",
        "grounding": {
            "value": "niece obtained durable POA in late 2023 and made unauthorized money-order purchases on Dorothy's Social Security income through early 2024",
            "evidence_basis": "FinCEN FTA_IDENTITY_2024 Abuse of Access (T7): misuse of legal authority granted via POA; overlaps with ELDER_FINANCIAL_EXPLOITATION advisory",
            "confidence": "INFERRED",
            "source_ids": ["fincen_2024_identity_fta", "fincen_sar_key_terms"],
        },
        "extra_source_ids": ["fincen_2024_identity_fta"],
        "fraud_vector": "power_of_attorney_abuse",
        "typology_code": "FTA_IDENTITY_2024_T7",
        "archetype": "unbanked",
        "language": "en",
    },
    "gig_worker": {
        "persona_id": "gig_001",
        "event_tag": "platform_refusal_records_id_theft_dispute_2024",
        "grounding_key": "fraud_exposure_refusal_to_cooperate",
        "grounding": {
            "value": "after the 2024 SIM-swap ATO, platform customer-support declined to produce transaction-log records DeShawn requested to support his identity-theft affidavit",
            "evidence_basis": "FinCEN FTA_IDENTITY_2024 Refusal to Cooperate (T8): entity refusing to provide information required for fraud investigation",
            "confidence": "INFERRED",
            "source_ids": ["fincen_2024_identity_fta"],
        },
        "extra_source_ids": [],
        "fraud_vector": "refusal_to_cooperate",
        "typology_code": "FTA_IDENTITY_2024_T8",
        "archetype": "gig_worker",
        "language": "en",
    },
    "itin": {
        "persona_id": "itin_010",
        "event_tag": "wage_confiscation_braider_intermediary_recurring",
        "grounding_key": "fraud_exposure_wage_confiscation",
        "grounding": {
            "value": "controlling intermediary (senior salon operator) withholds a portion of Fatou's braiding earnings each week under threat of immigration-status disclosure; she records the full gross on her ITIN Schedule C but sees a reduced net in hand",
            "evidence_basis": "FinCEN SAR Advisory on Human Trafficking and Smuggling (2014 FIN-2014-A008): wage confiscation and coerced labor indicators among informal-economy migrants",
            "confidence": "INFERRED",
            "source_ids": ["fincen_sar_key_terms", "fincen_2024_identity_fta"],
        },
        "extra_source_ids": ["fincen_sar_key_terms"],
        "fraud_vector": "wage_confiscation",
        "typology_code": "SAR_ADVISORY_HUMAN_TRAFFICKING",
        "archetype": "itin",
        "language": "wo",
    },
}


def patch_personas():
    for archetype, spec in PATCHES.items():
        path = V4 / archetype / "personas" / "persona_profiles.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for p in data["personas"]:
            if p["persona_id"] != spec["persona_id"]:
                continue
            # Add grounding entry
            p.setdefault("grounding", {})[spec["grounding_key"]] = spec["grounding"]
            # Add event to family_crisis_history
            fch = p.setdefault("family_crisis_history", [])
            if spec["event_tag"] not in fch:
                fch.append(spec["event_tag"])
            # Add any new source_ids
            ps = p.setdefault("persona_source_ids", [])
            for sid in spec["extra_source_ids"]:
                if sid not in ps:
                    ps.append(sid)
            print(f"[{archetype}] patched {spec['persona_id']} — added {spec['grounding_key']} + event {spec['event_tag']}")
            break
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def synthesize_rows() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    synth_frames = []
    for archetype, spec in PATCHES.items():
        src = pd.read_parquet(V4 / archetype / "adaptive" / "transactions_adapted.parquet")
        host = src[src["persona_id"] == spec["persona_id"]].copy()
        if host.empty:
            raise RuntimeError(f"No rows for host persona {spec['persona_id']}")
        # Sample PER_CODE rows with replacement from the host persona's transactions
        picks = host.sample(n=PER_CODE, replace=True, random_state=SEED).reset_index(drop=True)
        picks["data_uuid"] = [str(uuid.uuid4()) for _ in range(PER_CODE)]
        picks["is_fraud"] = 1
        picks["fraud_vector"] = spec["fraud_vector"]
        picks["fraud_vector_typology_ref"] = spec["typology_code"]
        picks["narrative_text"] = ""
        if "detected_language_hints" in picks.columns:
            picks["detected_language_hints"] = [np.array([spec["language"]], dtype=object)] * len(picks)
        # Force the configured language for consistency with the event framing
        picks["language"] = spec["language"]
        picks["dataset_version"] = "v4.1"
        synth_frames.append(picks)
        print(f"[{archetype}] synthesized {len(picks)} rows for {spec['typology_code']} "
              f"(host={spec['persona_id']}, vector={spec['fraud_vector']}, lang={spec['language']})")
    synth = pd.concat(synth_frames, ignore_index=True)
    return synth


def build_adaption_jsonl(synth: pd.DataFrame) -> Path:
    rows = []
    for arch, spec in PATCHES.items():
        ppath = V4 / arch / "personas" / "persona_profiles.json"
        personas = json.loads(ppath.read_text(encoding="utf-8"))["personas"]
        persona_summary = next(p["summary"] for p in personas if p["persona_id"] == spec["persona_id"])

        sub = synth[synth["persona_id"] == spec["persona_id"]]
        for _, r in sub.iterrows():
            amt = float(r["transaction_amount_usd"])
            fee = float(r.get("fee_amount_usd") or 0.0)
            instr = str(r.get("instrument") or spec["fraud_vector"])
            hour = int(r.get("hour_of_day") or 12)
            dow = str(r.get("day_of_week_name") or r.get("day_of_week") or "Mon")
            dsl = int(r.get("days_since_last_txn") or 7)

            prompt = (
                "Write a realistic first-person narrative (3-5 sentences) from this persona "
                "describing a fraudulent transaction that just occurred. Use the persona's voice, "
                "cultural context, and primary language. Hint at the scam mechanic without naming "
                "it explicitly.\n\n"
                f"Persona ({spec['archetype']}):\n{persona_summary}\n\n"
                f"Fraud typology: {spec['typology_code']} ({spec['fraud_vector']}).\n\n"
                "Transaction:\n"
                + json.dumps({
                    "amount_usd": amt,
                    "fee_usd": fee,
                    "instrument": instr,
                    "fraud_vector": spec["fraud_vector"],
                    "hour_of_day": hour,
                    "day_of_week": dow[:3],
                    "days_since_last": dsl,
                    "is_fraud": 1,
                }, ensure_ascii=False)
                + "\n\n"
                f"Language to write in: {spec['language']}. Include one emotional beat consistent "
                "with the transaction (worry, shame, obligation, resignation). Return just the "
                "narrative text, no preamble."
            )
            rows.append({
                "prompt": prompt,
                "completion": "",
                "data_uuid": r["data_uuid"],
                "persona_id": spec["persona_id"],
                "archetype": spec["archetype"],
                "is_fraud": 1,
                "language": spec["language"],
                "fraud_vector_typology_ref": spec["typology_code"],
            })
    out_path = OUT / "missing_typology_for_adaption.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Adaption JSONL: {out_path}  ({len(rows)} prompts)")
    return out_path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("--- patching personas ---")
    patch_personas()
    print("\n--- synthesizing rows ---")
    synth = synthesize_rows()
    synth_path = OUT / "missing_typology_rows.parquet"
    synth.to_parquet(synth_path, index=False, engine="pyarrow")
    print(f"Synthetic rows: {synth_path}  ({len(synth)} rows)")
    print("\n--- building Adaption JSONL ---")
    build_adaption_jsonl(synth)
    print(f"\nNext:")
    print("  ADAPTION_API_KEY=... adaption datasets upload --file datasets_v4/v4_1/missing_typology_for_adaption.jsonl "
          "--name fraud-v4_1-missing-typology")
    print("  (or plug into adaptive_v4.py submit flow pointed at this JSONL)")
    print("  then merge downloaded narratives via v4_1_merge_missing.py (follow-up script).")


if __name__ == "__main__":
    main()