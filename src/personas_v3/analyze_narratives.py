"""
Analysis of v3 narrative-filled dataset.

Answers five questions:
  1. How many languages did Adaption write narratives in (tagged vs detected)?
  2. Prompt-element propagation rate — % of narratives that contain each
     prompt-supplied signal (amount, persona name, corridor, platform, etc.)
  3. Grade distribution achieved vs target (evidence of forcing where
     sources were thin)
  4. Problems reported — empty narratives, unique fraud_vector + typology
     coverage, rows where detected language doesn't match tagged language
  5. v2 vs v3 overlap — v2 coherence-violation taxonomy recast against
     structural checks we can compute on v3 without paid coherence scoring

Writes a summary to datasets_v3/exports/analysis_report.json and prints a
human-readable summary.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 42
ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "datasets_v3"
V2 = ROOT / "datasets_v2"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def _load_v3_all() -> pd.DataFrame:
    frames = []
    for arch in ARCHETYPES:
        df = pd.read_parquet(V3 / arch / "adaptive" / "transactions_adapted.parquet")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _load_personas() -> dict[str, dict]:
    out = {}
    for arch in ARCHETYPES:
        doc = json.loads((V3 / arch / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))
        for p in doc["personas"]:
            out[p["persona_id"]] = p
    return out


def _safe_detect(text: str) -> str | None:
    try:
        if not text or len(text) < 40:
            return None
        return detect(text)
    except LangDetectException:
        return None


# ── Q1: Languages ────────────────────────────────────────────────────────────

def q1_languages(df: pd.DataFrame) -> dict:
    tagged = df["language"].value_counts().to_dict()
    df["detected_lang"] = df["narrative_text"].astype(str).apply(_safe_detect)
    detected = df["detected_lang"].value_counts(dropna=False).to_dict()
    # Match rate: tagged vs detected (where both present)
    both = df.dropna(subset=["detected_lang"]).copy()
    match = (both["language"] == both["detected_lang"]).mean() if len(both) else 0.0
    return {
        "n_unique_tagged_languages": len([k for k in tagged if k]),
        "tagged_language_counts": tagged,
        "n_unique_detected_languages": len([k for k in detected if k and k == k]),
        "detected_language_counts": {str(k): int(v) for k, v in detected.items()},
        "tag_detect_match_rate": round(float(match), 3),
    }


# ── Q2: Prompt-element propagation ───────────────────────────────────────────

def q2_propagation(df: pd.DataFrame, personas: dict) -> dict:
    """Per-row check of how many prompt signals appear in the narrative."""
    checks = {
        "amount_rounded_in_text": [],
        "amount_exact_in_text":   [],
        "persona_first_name_in_text": [],
        "corridor_keyword_in_text":   [],     # remittance only
        "platform_name_in_text":      [],     # gig_worker only
        "instrument_in_text":         [],
        "day_of_week_in_text":        [],
        "hour_class_in_text":         [],     # morning/afternoon/evening/night
    }
    for _, row in df.iterrows():
        narr = str(row.get("narrative_text", "")).lower()
        persona = personas.get(row["persona_id"], {})

        amt = float(row.get("transaction_amount_usd", 0) or 0)
        # rounded: check if near-integer representation surfaces (allow "$123", "123", "one hundred" isn't counted — too broad)
        amt_round = f"{int(round(amt))}"
        amt_round_comma = f"{int(round(amt)):,}"  # "1,254"
        amt_exact  = f"{amt:.2f}"
        amt_dollars_cents = f"{int(amt)} dollars"
        checks["amount_rounded_in_text"].append(int(any(s in narr for s in [amt_round, amt_round_comma])))
        checks["amount_exact_in_text"].append(int(amt_exact in narr))

        # persona first name
        name = persona.get("name", "").split()[0].lower() if persona.get("name") else ""
        checks["persona_first_name_in_text"].append(int(bool(name) and name in narr))

        # corridor — only for remittance
        corridor = persona.get("corridor_country", "") or ""
        if row["archetype"] == "remittance" and corridor:
            # extract anchor word: e.g. "Haiti (Port-au-Prince)" -> check for "haiti" OR "port-au-prince"
            m = re.match(r"([^(]+)", corridor)
            anchors = []
            if m: anchors.append(m.group(1).strip().lower())
            inner = re.search(r"\(([^)]+)\)", corridor)
            if inner: anchors.append(inner.group(1).strip().lower())
            checks["corridor_keyword_in_text"].append(int(any(a in narr for a in anchors if a)))
        else:
            checks["corridor_keyword_in_text"].append(None)

        # platform — gig_worker only, pull top platform from platform_mix
        if row["archetype"] == "gig_worker":
            pm = persona.get("platform_mix") or {}
            if pm:
                top_platform = max(pm.items(), key=lambda kv: kv[1])[0].lower()
                checks["platform_name_in_text"].append(int(top_platform in narr))
            else:
                checks["platform_name_in_text"].append(None)
        else:
            checks["platform_name_in_text"].append(None)

        # instrument — check row's instrument
        inst = str(row.get("instrument", "")).lower()
        if inst and inst != "unknown":
            core = inst.split("(")[0].strip()  # "Western Union (in-person)" -> "western union"
            checks["instrument_in_text"].append(int(core in narr))
        else:
            checks["instrument_in_text"].append(None)

        # day of week
        dow_name = str(row.get("day_of_week_name", "")).lower()
        if dow_name:
            full = {"mon": "monday", "tue": "tuesday", "wed": "wednesday", "thu": "thursday",
                    "fri": "friday", "sat": "saturday", "sun": "sunday"}.get(dow_name[:3], dow_name)
            checks["day_of_week_in_text"].append(int(dow_name in narr or full in narr))
        else:
            checks["day_of_week_in_text"].append(None)

        # hour class
        h = int(row.get("hour_of_day", 12))
        if   h < 6:  classes = ["night", "early morning", "pre-dawn", "late"]
        elif h < 12: classes = ["morning", "am"]
        elif h < 17: classes = ["afternoon", "noon", "lunch"]
        elif h < 21: classes = ["evening", "after work", "pm"]
        else:        classes = ["night", "late", "evening"]
        checks["hour_class_in_text"].append(int(any(c in narr for c in classes)))

    # Aggregate — skip None (archetype-specific checks)
    out = {}
    for key, vals in checks.items():
        filtered = [v for v in vals if v is not None]
        if filtered:
            out[key] = {
                "n_applicable": len(filtered),
                "n_match": sum(filtered),
                "rate": round(sum(filtered) / len(filtered), 3),
            }
    return out


# ── Q3: Grade distribution achieved vs target ────────────────────────────────

def q3_grade_distribution(df: pd.DataFrame) -> dict:
    targets = {
        "remittance": {"A": (0.15, 0.20), "B": (0.25, 0.30), "C": (0.30, 0.35), "D": (0.15, 0.25)},
        "gig_worker": {"A": (0.20, 0.25), "B": (0.15, 0.20), "C": (0.20, 0.25), "D": (0.30, 0.40)},
        "unbanked":   {"A": (0.25, 0.30), "B": (0.15, 0.20), "C": (0.15, 0.20), "D": (0.30, 0.40)},
        "itin":       {"A": (0.10, 0.15), "B": (0.35, 0.40), "C": (0.10, 0.15), "D": (0.30, 0.40)},
    }
    out = {}
    for arch, tgt in targets.items():
        sub = df[df["archetype"] == arch]
        actual = sub["behavioral_evidence_grade"].value_counts(normalize=True).to_dict()
        gaps = {}
        for g, (lo, hi) in tgt.items():
            a = actual.get(g, 0.0)
            in_range = lo <= a <= hi
            gaps[g] = {
                "target_range": [lo, hi],
                "actual": round(a, 3),
                "in_range": in_range,
                "gap_to_nearest_bound": round(0 if in_range else (lo - a) if a < lo else (a - hi), 3),
            }
        out[arch] = gaps
    return out


# ── Q4: Problems reported ────────────────────────────────────────────────────

def q4_problems(df: pd.DataFrame) -> dict:
    empty = df[df["narrative_text"].astype(str).str.len() == 0]
    short = df[df["narrative_text"].astype(str).str.len().between(1, 60)]
    unique_fv = df["fraud_vector"].dropna().unique()
    fraud_only = df[df["is_fraud"] == 1]
    unique_typology = fraud_only["fraud_vector_typology_ref"].dropna().unique()

    # Languages where tag != detected
    if "detected_lang" not in df.columns:
        df["detected_lang"] = df["narrative_text"].astype(str).apply(_safe_detect)
    lang_mismatch = df.dropna(subset=["detected_lang"]).query("language != detected_lang")

    # Persona coverage in generated rows
    persona_coverage = df.groupby(["archetype", "persona_id"]).size().reset_index(name="n")
    missing_personas = []
    for arch in ARCHETYPES:
        doc = json.loads((V3 / arch / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))
        generated = set(persona_coverage[persona_coverage["archetype"] == arch]["persona_id"])
        for p in doc["personas"]:
            if p["persona_id"] not in generated:
                missing_personas.append({"archetype": arch, "persona_id": p["persona_id"]})

    return {
        "empty_narratives": int(len(empty)),
        "short_narratives_under_60_chars": int(len(short)),
        "n_unique_fraud_vectors_used": int(len(unique_fv)),
        "n_unique_typology_codes_used": int(len(unique_typology)),
        "typology_codes_exercised": sorted(unique_typology.tolist()),
        "language_tag_mismatch_count": int(len(lang_mismatch)),
        "language_tag_mismatch_rate": round(len(lang_mismatch) / max(len(df), 1), 3),
        "missing_personas": missing_personas,
        "per_archetype_persona_coverage": persona_coverage.groupby("archetype")["n"].agg(["count", "min", "max", "mean"]).to_dict(orient="index"),
    }


# ── Q5: v2 violation taxonomy vs v3 structural check ─────────────────────────

VIOLATION_BUCKETS = {
    "cadence":    r"cadence|freq|interval|biweekly|monthly|weekly|days|frequency",
    "amount":     r"amount|loss tolerance|transaction value|sum|quant",
    "channel":    r"channel|instrument|platform|service|method|provider",
    "hour_time":  r"hour|time|timing|\bam\b|\bpm\b|morning|night|evening|afternoon",
    "language":   r"language|spanish|english|creole|linguistic",
    "fraud_type": r"fraud|scam|typology|laundering|money mule",
    "fee":        r"fee|charge|markup|cost",
    "tenure_age": r"tenure|account.?age|history|years",
    "device_sim": r"device|phone|sim|handset",
    "persona_mismatch": r"persona|profile|identity|context|inconsistent",
}


def _classify_violation(text: str) -> list[str]:
    text = text.lower()
    hits = [bucket for bucket, pat in VIOLATION_BUCKETS.items() if re.search(pat, text)]
    return hits or ["other"]


def q5_v2_vs_v3(df: pd.DataFrame) -> dict:
    # Load all v2 violations from coherence_report.parquet
    v2_violations: list[str] = []
    for arch in ARCHETYPES:
        p = V2 / arch / "persona_verification" / "coherence_report.parquet"
        if not p.exists():
            continue
        sub = pd.read_parquet(p)
        for vstr in sub["violations"].dropna():
            try:
                lst = json.loads(vstr)
                v2_violations.extend(lst)
            except json.JSONDecodeError:
                continue

    v2_bucket_counter = Counter()
    for v in v2_violations:
        for b in _classify_violation(v):
            v2_bucket_counter[b] += 1

    # V3 structural checks — compute per-bucket "how many rows violate this concern"
    v3_checks = {
        "cadence":    int((df["days_since_last_txn"] > 60).sum()),           # unrealistic long gap
        "amount":     int((df["transaction_amount_usd"] <= 0).sum()),         # zero/negative amount
        "channel":    int(df["instrument"].astype(str).str.lower().eq("unknown").sum()),
        "hour_time":  int(((df["hour_of_day"] < 0) | (df["hour_of_day"] > 23)).sum()),
        "language":   int(df["language"].astype(str).eq("").sum()),
        "fraud_type": int((df["is_fraud"] == 1).sum() - df[df["is_fraud"] == 1]["fraud_vector"].astype(str).str.len().gt(0).sum()),
        "fee":        int((df["fee_amount_usd"] < 0).sum()),
        "tenure_age": int((df["account_age_days"] < 30).sum()),
        "device_sim": int(df["device_type"].astype(str).eq("unknown").sum()),
        "persona_mismatch": int(df["persona_id"].isna().sum()),
    }

    # v2 buckets where v3 has 0 structural evidence = v2 problem *potentially* solved
    buckets_in_v2 = set(v2_bucket_counter.keys())
    v3_clean = {b for b, v in v3_checks.items() if v == 0}
    potentially_solved = sorted(buckets_in_v2 & v3_clean)
    remaining_or_new = sorted((buckets_in_v2 & set(v3_checks.keys())) - v3_clean)

    return {
        "v2_violations_total": len(v2_violations),
        "v2_bucket_distribution_pct": {
            k: round(100 * v / len(v2_violations), 1) for k, v in v2_bucket_counter.most_common()
        },
        "v3_structural_check_raw_counts": v3_checks,
        "v2_buckets_potentially_addressed_in_v3": potentially_solved,
        "v2_buckets_still_structurally_present_in_v3": remaining_or_new,
        "caveat": "v3 has no coherence scoring run yet; these are structural checks only. True violation parity requires running src/personas/persona_verify.py against v3 data.",
    }


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("Loading v3 dataset...")
    df = _load_v3_all()
    personas = _load_personas()
    print(f"  {len(df)} rows across {len(ARCHETYPES)} archetypes\n")

    print("Q1: Language analysis...")
    q1 = q1_languages(df)
    print(f"  tagged languages: {q1['n_unique_tagged_languages']}")
    print(f"  detected languages: {q1['n_unique_detected_languages']}")
    print(f"  tag<->detect match rate: {q1['tag_detect_match_rate']:.1%}\n")

    print("Q2: Prompt-propagation rates...")
    q2 = q2_propagation(df, personas)
    for k, v in q2.items():
        print(f"  {k:35s} {v['rate']:.1%}  ({v['n_match']}/{v['n_applicable']})")
    print()

    print("Q3: Grade distribution vs target...")
    q3 = q3_grade_distribution(df)
    for arch, grades in q3.items():
        print(f"  {arch}:")
        for g, info in grades.items():
            status = "[OK]" if info["in_range"] else "[off]"
            print(f"    {g}: actual={info['actual']:.1%} target={info['target_range'][0]:.0%}-{info['target_range'][1]:.0%}  {status}")
    print()

    print("Q4: Problems reported...")
    q4 = q4_problems(df)
    print(f"  empty narratives:            {q4['empty_narratives']}")
    print(f"  short (<60 chars):           {q4['short_narratives_under_60_chars']}")
    print(f"  unique fraud_vectors used:   {q4['n_unique_fraud_vectors_used']}")
    print(f"  unique typology codes used:  {q4['n_unique_typology_codes_used']}")
    print(f"  typology codes: {q4['typology_codes_exercised']}")
    print(f"  language tag<->detected mismatch: {q4['language_tag_mismatch_count']} rows ({q4['language_tag_mismatch_rate']:.1%})")
    print(f"  missing personas: {len(q4['missing_personas'])}\n")

    print("Q5: v2 vs v3 problem taxonomy...")
    q5 = q5_v2_vs_v3(df)
    print(f"  v2 violations total: {q5['v2_violations_total']}")
    print(f"  v2 distribution by bucket:")
    for k, v in q5["v2_bucket_distribution_pct"].items():
        print(f"    {k:20s} {v}%")
    print(f"  v3 structural check raw counts:")
    for k, v in q5["v3_structural_check_raw_counts"].items():
        print(f"    {k:20s} {v}")
    print(f"  v2 buckets potentially addressed in v3: {q5['v2_buckets_potentially_addressed_in_v3']}")
    print(f"  v2 buckets still structurally present:  {q5['v2_buckets_still_structurally_present_in_v3']}")

    report = {"q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5}
    out_path = V3 / "exports" / "analysis_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nReport -> {out_path}")


if __name__ == "__main__":
    main()
