"""
Parse Adaption Labs output JSONL into structured artifacts.

Inputs (per archetype):
  datasets_v2/{archetype}/expanded_world/adapted_output.jsonl
  datasets_v2/{archetype}/persona_verification/adapted_output.jsonl

Outputs:
  datasets_v2/{archetype}/expanded_world/conditioning_schema.parquet
      one row per persona, with parsed JSON columns
      (transaction_calendar, device_fingerprint_evolution, remittance_cadence,
       income_seasonality, communication_patterns) stored as JSON strings —
       TabDDPM v2 generator reads these as conditioning inputs.

  datasets_v2/{archetype}/persona_verification/coherence_report.parquet
      one row per transaction with coherence_score, violations, rationale.
  datasets_v2/{archetype}/persona_verification/flagged_for_regen.parquet
      subset with coherence_score < 0.6.

  datasets_v2/coherence_summary.json  overall pass/flag stats per archetype.

Usage:
  python src/personas/parse_outputs.py --all
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "datasets_v2"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
COHERENCE_FLAG_THRESHOLD = 0.6


def extract_json(blob: str) -> dict | None:
    if not blob:
        return None
    m = re.search(r"```json\s*(\{.*?\})\s*```", blob, re.DOTALL)
    candidate = m.group(1) if m else blob.strip()
    # Find outermost JSON object if loose text surrounds it
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(candidate[start:end + 1])
    except json.JSONDecodeError:
        return None


def parse_expand_world(archetype: str) -> pd.DataFrame:
    path = DATA_ROOT / archetype / "expanded_world" / "adapted_output.jsonl"
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            parsed = extract_json(rec.get("enhanced_completion", "")) or {}
            rows.append({
                "persona_id": rec.get("persona_id"),
                "archetype": rec.get("archetype"),
                "transaction_calendar": json.dumps(parsed.get("transaction_calendar"), ensure_ascii=False),
                "device_fingerprint_evolution": json.dumps(parsed.get("device_fingerprint_evolution"), ensure_ascii=False),
                "remittance_cadence": json.dumps(parsed.get("remittance_cadence"), ensure_ascii=False),
                "income_seasonality": json.dumps(parsed.get("income_seasonality"), ensure_ascii=False),
                "communication_patterns": json.dumps(parsed.get("communication_patterns"), ensure_ascii=False),
                "parsed_ok": bool(parsed),
            })
    df = pd.DataFrame(rows)
    out = DATA_ROOT / archetype / "expanded_world" / "conditioning_schema.parquet"
    df.to_parquet(out, index=False)
    return df


def parse_persona_verify(archetype: str) -> pd.DataFrame:
    src_path = DATA_ROOT / archetype / "persona_verification" / "adapted_output.jsonl"
    upload_path = DATA_ROOT / archetype / "persona_verification" / "for_adaption.jsonl"
    upload_df = pd.read_json(upload_path, lines=True)
    upload_by_prompt = {r["prompt"]: r for _, r in upload_df.iterrows()}

    rows = []
    with src_path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            parsed = extract_json(rec.get("enhanced_completion", "")) or {}
            score = parsed.get("coherence_score")
            try:
                score = float(score) if score is not None else None
            except (TypeError, ValueError):
                score = None

            meta = upload_by_prompt.get(rec.get("prompt"), {})
            rows.append({
                "persona_id": rec.get("persona_id") or meta.get("persona_id"),
                "data_uuid": meta.get("data_uuid"),
                "archetype": rec.get("archetype") or meta.get("archetype"),
                "source": meta.get("source"),
                "coherence_score": score,
                "violations": json.dumps(parsed.get("violations", []), ensure_ascii=False),
                "rationale": parsed.get("rationale"),
                "parsed_ok": bool(parsed),
            })

    df = pd.DataFrame(rows)
    base = DATA_ROOT / archetype / "persona_verification"
    df.to_parquet(base / "coherence_report.parquet", index=False)

    flagged = df[(df["coherence_score"].notna()) & (df["coherence_score"] < COHERENCE_FLAG_THRESHOLD)]
    flagged.to_parquet(base / "flagged_for_regen.parquet", index=False)
    return df


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", default=True)
    parser.parse_args()

    summary = {}
    for arch in ARCHETYPES:
        print(f"\n=== {arch} ===")
        ew = parse_expand_world(arch)
        print(f"  expand_world: parsed {ew['parsed_ok'].sum()}/{len(ew)} personas")

        pv = parse_persona_verify(arch)
        n = len(pv)
        parsed_ok = int(pv["parsed_ok"].sum())
        with_score = pv["coherence_score"].notna().sum()
        mean_score = pv["coherence_score"].dropna().mean() if with_score else None
        flagged = int((pv["coherence_score"].dropna() < COHERENCE_FLAG_THRESHOLD).sum())
        print(f"  persona_verify: {parsed_ok}/{n} parsed, {with_score} with score, mean={mean_score:.3f}" if mean_score is not None else f"  persona_verify: {parsed_ok}/{n} parsed, 0 with score")
        print(f"  flagged for regen: {flagged}")
        summary[arch] = {
            "n_rows": n,
            "parsed_ok": parsed_ok,
            "with_score": int(with_score),
            "mean_coherence": round(float(mean_score), 3) if mean_score is not None else None,
            "flagged_for_regen": flagged,
            "flag_rate": round(flagged / with_score, 3) if with_score else None,
        }

    (DATA_ROOT / "coherence_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary -> {DATA_ROOT / 'coherence_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())