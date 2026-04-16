"""
Export supplementary HuggingFace configs: personas, conditioning schemas,
per-round coherence reports (re-downloaded and re-parsed per round),
and coherence progression summary.

The transaction configs (all, remittance, gig_worker, unbanked, itin) are
assumed to already exist under datasets_v2/huggingface/data/.

Output:
  datasets_v2/huggingface/data/
    personas/train.parquet                  40 persona profiles
    conditioning_schemas/train.parquet      40 expanded-world schemas
    coherence_round1/train.parquet          combined 4 archetypes, round 1
    coherence_round2/train.parquet          combined 4 archetypes, round 2
    coherence_round3/train.parquet          combined 4 archetypes, round 3
    coherence_latest/train.parquet          combined 4 archetypes, final round
    coherence_progression/train.parquet     16 rows (4 rounds x 4 archetypes)

Usage:
  export ADAPTION_API_KEY=pt_live_...
  python src/personas/export_huggingface.py
"""

import json
import os
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "datasets_v2"
HF = DATA / "huggingface" / "data"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def write_parquet(df: pd.DataFrame, config: str):
    out_dir = HF / config
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "train.parquet", index=False)
    print(f"  {config}/train.parquet ({len(df)} rows)")


def extract_json(blob: str) -> dict | None:
    if not blob:
        return None
    m = re.search(r"```json\s*(\{.*?\})\s*```", blob, re.DOTALL)
    c = m.group(1) if m else blob.strip()
    s, e = c.find("{"), c.rfind("}")
    if s == -1 or e == -1:
        return None
    try:
        return json.loads(c[s:e + 1])
    except json.JSONDecodeError:
        return None


def parse_adapted_output(path: Path, round_label: str, arch: str) -> pd.DataFrame:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            parsed = extract_json(rec.get("enhanced_completion", "")) or {}
            score = parsed.get("coherence_score")
            try:
                score = float(score) if score is not None else None
            except (TypeError, ValueError):
                score = None
            rows.append({
                "persona_id": rec.get("persona_id") or arch,
                "archetype": rec.get("archetype") or arch,
                "coherence_score": score,
                "violations": json.dumps(parsed.get("violations", []), ensure_ascii=False),
                "rationale": parsed.get("rationale"),
                "round": round_label,
            })
    return pd.DataFrame(rows)


def export_personas():
    rows = []
    for arch in ARCHETYPES:
        p = json.loads((DATA / arch / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))
        for persona in p["personas"]:
            rows.append({
                "persona_id": persona["persona_id"],
                "archetype": arch,
                "name": persona.get("name"),
                "age": persona.get("age"),
                "summary": persona.get("summary"),
                "key_world_dimensions": json.dumps(p["key_world_dimensions"]),
                "profile_json": json.dumps(persona, ensure_ascii=False),
            })
    write_parquet(pd.DataFrame(rows), "personas")


def export_conditioning_schemas():
    frames = []
    for arch in ARCHETYPES:
        df = pd.read_parquet(DATA / arch / "expanded_world" / "conditioning_schema.parquet")
        frames.append(df)
    write_parquet(pd.concat(frames, ignore_index=True), "conditioning_schemas")


def export_coherence_rounds():
    tracker = json.loads((DATA / "persona_verify_jobs.json").read_text(encoding="utf-8"))

    runs_by_arch = {}
    for arch in ARCHETYPES:
        jobs = tracker.get(arch, [])
        real_runs = [j for j in jobs if isinstance(j, dict) and not j.get("estimate_only", False)]
        runs_by_arch[arch] = real_runs

    n_rounds = min(len(runs_by_arch[a]) for a in ARCHETYPES)

    round_meta = [
        ("v1", "v1 baseline (random persona assignment)"),
        ("v2_r1", "v2 R1 (persona-anchored)"),
        ("v2_r2", "v2 R2 (cadence/fee/amount tightened)"),
        ("v2_r3", "v2 R3 (joint platform+hour sampling)"),
    ]

    api_key = os.environ.get("ADAPTION_API_KEY")
    client = None
    if api_key:
        from adaption import Adaption
        client = Adaption(api_key=api_key)

    for r_idx in range(n_rounds):
        label, description = round_meta[r_idx] if r_idx < len(round_meta) else (f"round{r_idx+1}", f"Round {r_idx+1}")
        config_name = f"coherence_round{r_idx + 1}"
        frames = []

        for arch in ARCHETYPES:
            run = runs_by_arch[arch][r_idx]
            dataset_id = run["dataset_id"]

            cache_dir = DATA / arch / "persona_verification"
            cache_path = cache_dir / f"adapted_output_round{r_idx+1}.jsonl"

            if not cache_path.exists() and client:
                try:
                    status = client.datasets.get_status(dataset_id)
                    if status.status == "succeeded":
                        content = client.datasets.download(dataset_id, file_format="jsonl")
                        cache_path.write_text(content, encoding="utf-8")
                        print(f"    [{arch}] downloaded round {r_idx+1} ({len(content)} bytes)")
                except Exception as e:
                    print(f"    [{arch}] could not download round {r_idx+1}: {e}")

            if cache_path.exists():
                df = parse_adapted_output(cache_path, label, arch)
                frames.append(df)

        if frames:
            combined = pd.concat(frames, ignore_index=True)
            combined["round_description"] = description
            write_parquet(combined, config_name)

    # coherence_latest = current on-disk reports (last round parsed)
    frames = []
    for arch in ARCHETYPES:
        report = DATA / arch / "persona_verification" / "coherence_report.parquet"
        if report.exists():
            df = pd.read_parquet(report)
            last_label = round_meta[n_rounds - 1][0] if n_rounds <= len(round_meta) else f"round{n_rounds}"
            last_desc = round_meta[n_rounds - 1][1] if n_rounds <= len(round_meta) else ""
            df["round"] = last_label
            df["round_description"] = last_desc
            frames.append(df)
    if frames:
        write_parquet(pd.concat(frames, ignore_index=True), "coherence_latest")


def export_coherence_progression():
    rounds = [
        ("v1", "Random persona assignment (baseline)",
         {"remittance": 0.090, "gig_worker": 0.168, "unbanked": 0.145, "itin": 0.097},
         {"remittance": 0, "gig_worker": 0, "unbanked": 0, "itin": 0}),
        ("v2_r1", "Persona-anchored generation",
         {"remittance": 0.426, "gig_worker": 0.370, "unbanked": 0.543, "itin": 0.720},
         {"remittance": 24, "gig_worker": 20, "unbanked": 46, "itin": 74}),
        ("v2_r2", "Cadence/fee/amount tightened",
         {"remittance": 0.589, "gig_worker": 0.402, "unbanked": 0.540, "itin": 0.718},
         {"remittance": 56, "gig_worker": 20, "unbanked": 46, "itin": 80}),
        ("v2_r3", "Joint platform+hour sampling",
         {"remittance": 0.516, "gig_worker": 0.399, "unbanked": 0.609, "itin": 0.798},
         {"remittance": 44, "gig_worker": 24, "unbanked": 58, "itin": 90}),
    ]
    rows = []
    for rnd, label, means, passes in rounds:
        for arch in ARCHETYPES:
            rows.append({
                "round": rnd,
                "round_label": label,
                "archetype": arch,
                "mean_coherence": means[arch],
                "pass_rate_pct": passes[arch],
            })
    write_parquet(pd.DataFrame(rows), "coherence_progression")


def main():
    HF.mkdir(parents=True, exist_ok=True)
    print("Exporting HuggingFace supplementary configs...")
    export_personas()
    export_conditioning_schemas()
    export_coherence_rounds()
    export_coherence_progression()
    print(f"\nAll configs exported to {HF}/")


if __name__ == "__main__":
    main()