"""
v4.1 — Re-prompt the 52 rows whose v4 narrative_text is empty.

Uses the ORIGINAL prompts from datasets_v4/adaptive_combined/for_adaption.jsonl
(matched by data_uuid) so Adaption sees the same persona+transaction context
that was used for the 20k job. No prompt drift — just a retry on empties.

Output:
  datasets_v4/v4_1/empties_reprompt.jsonl     Adaption-ready JSONL (~52 rows)
  datasets_v4/v4_1/empties_manifest.csv       row identity + archetype breakdown
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
OUT = V4 / "v4_1"


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    empty_uuids: dict[str, str] = {}  # uuid -> archetype
    for a in ARCHETYPES:
        df = pd.read_parquet(V4 / a / "adaptive" / "transactions_adapted.parquet")
        nt = df["narrative_text"].fillna("").astype(str)
        for u in df.loc[nt.str.len() == 0, "data_uuid"]:
            empty_uuids[u] = a
    print(f"Empties to re-prompt: {len(empty_uuids)}")

    # Pull original prompts from the combined upload JSONL
    combined_prompt = V4 / "adaptive_combined" / "for_adaption.jsonl"
    picked = []
    with combined_prompt.open(encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = r.get("data_uuid", "")
            if u in empty_uuids:
                picked.append(r)

    print(f"Matched prompts found in combined for_adaption.jsonl: {len(picked)} / {len(empty_uuids)}")

    out_jsonl = OUT / "empties_reprompt.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in picked:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = pd.DataFrame([
        {"data_uuid": r["data_uuid"], "archetype": r.get("archetype", empty_uuids.get(r["data_uuid"], "")),
         "persona_id": r.get("persona_id", ""), "language": r.get("language", "")}
        for r in picked
    ])
    manifest_path = OUT / "empties_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    print(f"Wrote: {out_jsonl}  ({len(picked)} rows)")
    print(f"Wrote: {manifest_path}")
    print("\nPer-archetype:")
    if not manifest.empty:
        print(manifest["archetype"].value_counts().to_string())


if __name__ == "__main__":
    main()