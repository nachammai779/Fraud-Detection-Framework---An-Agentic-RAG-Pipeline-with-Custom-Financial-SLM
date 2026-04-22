"""
Lint v3 personas against sources.json and typology_registry.json.

Checks:
  1. Every source_id referenced in a persona resolves in sources.json
  2. Every typology code referenced in a grounding entry resolves in typology_registry.json
  3. Required persona keys present
  4. behavioral_evidence_grade is A/B/C/D
  5. persona_id prefix matches archetype
  6. No duplicate persona_ids within archetype
  7. Archetype in persona_source_ids source's applies-to list (i.e., we don't cite a source outside its declared archetype scope)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "datasets_v3"
SOURCES = V3 / "sources" / "sources.json"
TYPOLOGY = V3 / "sources" / "typology_registry.json"

REQUIRED = {"persona_id", "name", "age", "summary", "behavioral_evidence_grade",
            "persona_source_ids", "grounding", "language_mix"}
PREFIX = {"remittance": "rem_", "gig_worker": "gig_", "unbanked": "unb_", "itin": "itin_"}
VALID_GRADES = {"A", "B", "C", "D"}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    source_ids = {k for k in sources if not k.startswith("_")}

    typology = json.loads(TYPOLOGY.read_text(encoding="utf-8"))
    typology_codes = {k for k in typology if not k.startswith("_")}

    arch_to_sources: dict[str, set[str]] = {a: set() for a in PREFIX}
    for sid, meta in sources.items():
        if sid.startswith("_"):
            continue
        for a in meta.get("archetypes", []):
            if a in arch_to_sources:
                arch_to_sources[a].add(sid)

    def collect_source_refs(obj) -> set[str]:
        refs = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "source_ids" and isinstance(v, list):
                    refs.update(v)
                else:
                    refs.update(collect_source_refs(v))
        elif isinstance(obj, list):
            for item in obj:
                refs.update(collect_source_refs(item))
        return refs

    def collect_typology_refs(obj) -> set[str]:
        refs = set()
        if isinstance(obj, dict):
            for v in obj.values():
                refs.update(collect_typology_refs(v))
        elif isinstance(obj, list):
            for item in obj:
                refs.update(collect_typology_refs(item))
        elif isinstance(obj, str):
            for m in re.findall(r"(FTA_IDENTITY_2024_T\d+|SAR_ADVISORY_[A-Z0-9_]+)", obj):
                refs.add(m)
        return refs

    total_personas = 0
    for arch, prefix in PREFIX.items():
        path = V3 / arch / "personas" / "persona_profiles.json"
        if not path.exists():
            errors.append(f"[{arch}] missing persona_profiles.json")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        personas = doc.get("personas", [])
        seen_ids = set()
        for p in personas:
            total_personas += 1
            pid = p.get("persona_id", "<missing>")
            ctx = f"[{arch}/{pid}]"

            missing = REQUIRED - set(p.keys())
            if missing:
                errors.append(f"{ctx} missing required keys: {sorted(missing)}")

            if not pid.startswith(prefix):
                errors.append(f"{ctx} persona_id must start with {prefix!r}")

            if pid in seen_ids:
                errors.append(f"{ctx} duplicate persona_id within archetype")
            seen_ids.add(pid)

            grade = p.get("behavioral_evidence_grade")
            if grade not in VALID_GRADES:
                errors.append(f"{ctx} behavioral_evidence_grade={grade!r} not in A/B/C/D")

            psids = p.get("persona_source_ids") or []
            if grade == "D" and psids:
                warnings.append(f"{ctx} grade D persona has persona_source_ids={psids} (unusual)")
            if grade != "D" and not psids:
                errors.append(f"{ctx} grade {grade} persona has empty persona_source_ids")

            # 1. All referenced source_ids exist
            all_refs = set(psids) | collect_source_refs(p.get("grounding", {}))
            unknown = all_refs - source_ids
            if unknown:
                errors.append(f"{ctx} references unknown source_ids: {sorted(unknown)}")

            # 7. Cited sources are declared applicable to this archetype
            for sid in all_refs & source_ids:
                if sid not in arch_to_sources[arch]:
                    warnings.append(f"{ctx} cites {sid!r} but that source isn't declared for archetype {arch} in sources.json")

            # 2. Typology refs (if any embedded in grounding strings)
            typ_refs = collect_typology_refs(p.get("grounding", {}))
            unknown_typ = typ_refs - typology_codes
            if unknown_typ:
                errors.append(f"{ctx} references unknown typology codes: {sorted(unknown_typ)}")

    print(f"Scanned {total_personas} personas across {len(PREFIX)} archetypes.")
    print(f"  sources.json entries: {len(source_ids)}")
    print(f"  typology_registry.json codes: {len(typology_codes)}")
    print()

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ! {w}")
        print()

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  X {e}")
        return 1

    print("OK — no errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
