"""
Extract unbanked-conditioned empirical distributions from the FDIC 2023
Household Survey microdata, for grounding v3 unbanked personas.

Source:  datasets_v3/sources/pdfs/hh2023/
  - hh2023_analys.csv           (309 MB analytic microdata; local-only)
  - metadata/metadata.csv       (variable value labels)

Output:  datasets_v3/sources/extracts/fdic_2023_hh_microdata.json
  structured persona_dimensions: weighted percentages across the unbanked
  subpopulation (hunbnk==1) for every dimension relevant to persona synthesis.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HH = ROOT / "datasets_v3" / "sources" / "pdfs" / "hh2023"
CSV = HH / "hh2023_analys.csv"
META = HH / "metadata" / "metadata.csv"
OUT = ROOT / "datasets_v3" / "sources" / "extracts" / "fdic_2023_hh_microdata.json"

# Variables we want in the persona dimension map. (var -> description)
DIMS = {
    # demographics
    "pagegrp":   ("demographics", "age_group"),
    "praceeth":  ("demographics", "race_ethnicity"),
    "peducgrp":  ("demographics", "education"),
    "pempstat":  ("demographics", "employment_status"),
    "pnativ":    ("demographics", "citizenship_and_birthplace"),
    "gereg":     ("demographics", "geographic_region"),
    "hhtypev2":  ("demographics", "household_type"),
    "hhincome":  ("demographics", "family_income_bracket"),

    # financial behavior + vulnerability
    "hincvol":   ("vulnerability_signals", "monthly_income_volatility"),
    "hbilldq":   ("vulnerability_signals", "fell_behind_on_bills_past_12mo"),
    "hbnkprev":  ("financial_behavior", "previously_banked"),
    "hbnknew":   ("financial_behavior", "length_of_bank_account_ownership"),
    "hbnkaccm":  ("financial_behavior", "most_common_account_access_channel"),

    # alternative financial services use (past 12 months)
    "huse12cc":  ("financial_behavior", "used_nonbank_check_cashing_past_12mo"),
    "huse12mo":  ("financial_behavior", "used_nonbank_money_order_past_12mo"),
    "huse12pdl": ("financial_behavior", "used_payday_loan_past_12mo"),
    "huse12pwn": ("financial_behavior", "used_pawn_shop_loan_past_12mo"),
    "huse12rto": ("financial_behavior", "used_rent_to_own_past_12mo"),
    "huse12atl": ("financial_behavior", "used_auto_title_loan_past_12mo"),
    "huse2afstv1": ("financial_behavior", "any_nonbank_transaction_product_past_12mo"),
}

CATEGORY_ORDER = ["demographics", "financial_behavior", "vulnerability_signals"]


def load_value_labels() -> dict:
    md = pd.read_csv(META)
    labels: dict[str, dict[float, str]] = {}
    for _, row in md.iterrows():
        var = row["VariableName"]
        code = row["Code"]
        val = row["Value"]
        if pd.isna(var) or pd.isna(code) or pd.isna(val):
            continue
        # Only keep 2023 entries
        if row.get("in2023") != "y":
            continue
        labels.setdefault(var, {})[float(code)] = str(val)
    return labels


def weighted_pct(df: pd.DataFrame, var: str) -> list[tuple[float, float, int]]:
    """Return [(code, pct_weighted, n_raw)] sorted by weighted pct descending,
    for the population restricted to unbanked supplement respondents."""
    grp = df.groupby(var, dropna=False)
    out = []
    total_wt = df["hwhhwgt"].sum()
    for code, sub in grp:
        wt = sub["hwhhwgt"].sum()
        pct = 100.0 * wt / total_wt if total_wt > 0 else 0.0
        out.append((code, round(pct, 2), len(sub)))
    out.sort(key=lambda r: -r[1])
    return out


def format_variable(var: str, dist: list[tuple[float, float, int]],
                    labels: dict) -> dict:
    v_labels = labels.get(var, {})
    buckets = []
    for code, pct, n in dist:
        if pd.isna(code):
            label = "(missing)"
            code_out = None
        else:
            label = v_labels.get(float(code), f"(code={code})")
            code_out = int(code) if code == int(code) else float(code)
        buckets.append({
            "code": code_out,
            "label": label,
            "percent_weighted": pct,
            "n_raw": n,
        })
    return {"distribution": buckets}


def main():
    print(f"loading analytic CSV ({CSV.stat().st_size // (1024*1024)} MB) ...")
    cols = ["hunbnk", "hsupresp", "hwhhwgt", *DIMS.keys()]
    df = pd.read_csv(CSV, usecols=cols)
    print(f"  rows: {len(df):,}")
    df = df[df["hsupresp"] == 1]
    print(f"  supplement respondents: {len(df):,}")
    unbanked = df[df["hunbnk"] == 1].copy()
    banked = df[df["hunbnk"] == 2].copy()
    print(f"  unbanked rows:  {len(unbanked):,}  (weighted: {unbanked['hwhhwgt'].sum():,.0f})")
    print(f"  banked rows:    {len(banked):,}  (weighted: {banked['hwhhwgt'].sum():,.0f})")

    labels = load_value_labels()

    persona_dimensions: dict[str, dict] = {}
    for cat in CATEGORY_ORDER:
        persona_dimensions[cat] = {}

    for var, (category, field_name) in DIMS.items():
        dist = weighted_pct(unbanked, var)
        persona_dimensions[category][field_name] = {
            **format_variable(var, dist, labels),
            "variable": var,
            "source_ref": "codebook + analytic microdata (hunbnk==1, hsupresp==1, weighted hwhhwgt)",
            "confidence": "DIRECT",
            "n_raw_unbanked": int(len(unbanked)),
        }

    out_doc = {
        "source_id": "fdic_2023_hh_microdata",
        "archetype": "unbanked",
        "extraction_method": "weighted empirical distribution from analytic CSV, restricted to supplement respondents with hunbnk==1 (unbanked households)",
        "sample": {
            "n_households_supplement_respondents": int(len(df)),
            "n_unbanked_raw": int(len(unbanked)),
            "weighted_unbanked_households": int(unbanked["hwhhwgt"].sum()),
            "n_banked_raw": int(len(banked)),
            "weighted_banked_households": int(banked["hwhhwgt"].sum()),
            "national_unbanked_rate_weighted": round(
                100.0 * unbanked["hwhhwgt"].sum() / df["hwhhwgt"].sum(), 2
            ),
        },
        "persona_dimensions": persona_dimensions,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out_doc, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
