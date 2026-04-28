"""
Strip Adaption prompt-tag leakage from v4 narrative_text.

Some v4 rows have the "Additional Context Tags" block (archetype, persona_id,
data_uuid, is_fraud, language, [typology]) echoed into the narrative, separated
by newlines, commas, or spaces. The data_uuid is the reliable anchor (36-char
UUIDs never appear in real prose): we cut at its first occurrence, then
backtrack across any preceding separators, persona_id, and archetype tokens.

Cleans in place:
  datasets_v4/{archetype}/adaptive/transactions_adapted.parquet
  datasets_v4/exports/transactions_v4_20k.parquet
  datasets_v4/exports/transactions_v4_20k.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]

_SEP = " \n\r\t,;."


def _strip_one(text: str, archetype: str, persona_id: str, data_uuid: str) -> str:
    if not text or not data_uuid or data_uuid not in text:
        return text
    head = text[: text.find(data_uuid)]
    while True:
        prev = head
        head = head.rstrip(_SEP)
        if persona_id and head.endswith(persona_id):
            head = head[: -len(persona_id)]
            continue
        if archetype and head.endswith(archetype):
            head = head[: -len(archetype)]
            continue
        if head == prev:
            break
    return head.rstrip(_SEP)


def _strip_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = df["narrative_text"].fillna("").astype(str)
    cleaned = [
        _strip_one(str(t or ""), str(a), str(p), str(u))
        for t, a, p, u in zip(
            before, df["archetype"], df["persona_id"], df["data_uuid"]
        )
    ]
    df = df.copy()
    df["narrative_text"] = cleaned
    changed = int(sum(b != c for b, c in zip(before, cleaned)))
    return df, changed


def main() -> None:
    total_changed = 0

    for arch in ARCHETYPES:
        p = V4 / arch / "adaptive" / "transactions_adapted.parquet"
        if not p.exists():
            print(f"[{arch}] missing {p} — skipping")
            continue
        df = pd.read_parquet(p)
        if "archetype" not in df.columns:
            df["archetype"] = arch
        df, changed = _strip_frame(df)
        df.to_parquet(p, index=False, engine="pyarrow")
        total_changed += changed
        print(f"[{arch}] cleaned {changed}/{len(df)} rows -> {p}")

    bundle_parquet = V4 / "exports" / "transactions_v4_20k.parquet"
    bundle_csv = V4 / "exports" / "transactions_v4_20k.csv"
    if bundle_parquet.exists():
        df = pd.read_parquet(bundle_parquet)
        df, changed = _strip_frame(df)
        df.to_parquet(bundle_parquet, index=False, engine="pyarrow")
        print(f"[bundle] cleaned {changed}/{len(df)} rows -> {bundle_parquet}")
        if bundle_csv.exists():
            df.to_csv(bundle_csv, index=False)
            print(f"[bundle] rewrote CSV -> {bundle_csv}")

    print(f"\nTotal narrative rows modified: {total_changed}")


if __name__ == "__main__":
    main()