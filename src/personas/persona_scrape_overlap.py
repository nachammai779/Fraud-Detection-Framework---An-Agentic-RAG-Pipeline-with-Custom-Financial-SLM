"""
Quantify implicit overlap between v2 persona profiles and the scraped
seed_narratives.jsonl corpus per archetype.

For each persona, pulls a bag of signal tokens (services, corridors/platforms,
fraud vectors, languages) and checks which ones appear (case-insensitive
substring) in the concatenated scraped text for that archetype. Reports
per-persona match rate and per-archetype aggregates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "datasets_v2"
SCRAPE = ROOT / "src" / "scrapers" / "datasets"

LANG_ALIASES = {
    "es": ["spanish", "espanol", "español", "estafa", "remesa"],
    "en": ["english"],
    "vi": ["vietnamese", "tieng viet"],
    "ht": ["haitian", "creole", "kreyol"],
    "fr": ["french", "francais"],
    "hi": ["hindi", "bhai", "namaste"],
    "yo": ["yoruba", "nigeria"],
    "zh": ["chinese", "mandarin", "cantonese"],
    "tl": ["tagalog", "filipino"],
    "pt": ["portuguese", "portugues"],
    "ar": ["arabic"],
    "ko": ["korean"],
}

FRAUD_VECTOR_ALIASES = {
    "phone_scam": ["phone scam", "phone call", "called me", "phone fraud"],
    "romance_scam": ["romance", "dating scam", "lover", "girlfriend scam", "boyfriend scam"],
    "ice_call": ["ice", "immigration", "deportation"],
    "tech_support": ["tech support", "microsoft", "apple support"],
    "whatsapp_impersonation": ["whatsapp", "impersonat"],
    "courier_theft": ["courier", "theft", "robbed", "stolen"],
    "earthquake_aid": ["earthquake", "disaster", "relief"],
    "medical": ["hospital", "medical", "surgery", "medication", "diabetes"],
    "tuition": ["tuition", "school fees", "university", "college fee"],
    "wage_theft": ["wage theft", "unpaid", "never paid", "deactivat"],
    "account_deactivation": ["deactivat", "banned", "suspended"],
    "fake_irs": ["irs", "tax", "refund"],
    "check_fraud": ["check", "bounced", "returned"],
    "prepaid_card": ["prepaid", "gift card", "green dot", "netspend"],
    "kiosk_fraud": ["kiosk", "atm", "moneypass"],
}


def extract_persona_signals(p: dict, archetype: str) -> list[str]:
    """Pull token set for one persona. Lowercased, deduped."""
    sig = set()

    # Languages -> aliases
    for lg in p.get("language_mix", []):
        for alias in LANG_ALIASES.get(lg, [lg]):
            sig.add(alias.lower())

    # Corridor / location
    corridor = p.get("corridor_country", "")
    if corridor:
        m = re.match(r"([^(]+)", corridor)
        if m:
            sig.add(m.group(1).strip().lower())
        inner = re.search(r"\(([^)]+)\)", corridor)
        if inner:
            sig.add(inner.group(1).strip().lower())

    # Transfer services (remittance)
    tsl = p.get("transfer_service_loyalty", {})
    for key in ("primary", "secondary"):
        v = tsl.get(key)
        if isinstance(v, str) and v and v != "none":
            clean = re.sub(r"\s*\([^)]*\)", "", v).strip().lower()
            if clean:
                sig.add(clean)

    # Gig platform mix
    pm = p.get("platform_mix") or p.get("platforms") or []
    if isinstance(pm, dict):
        pm = list(pm.keys())
    for plat in pm:
        if isinstance(plat, str):
            sig.add(plat.lower())

    # Unbanked: prepaid card stack, income source
    for field in ("prepaid_card_stack", "income_source", "kiosk_location",
                  "documentation_status", "business_type",
                  "accountant_relationship", "daily_cashout_pattern"):
        v = p.get(field)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    sig.add(item.lower())
        elif isinstance(v, str):
            sig.add(v.lower())

    # Family crisis history / fraud events
    for event in p.get("family_crisis_history", []):
        if not isinstance(event, str):
            continue
        # Event strings look like "phone_scam_attempted_2024"
        ev = event.lower()
        for key, aliases in FRAUD_VECTOR_ALIASES.items():
            if key.split("_")[0] in ev or any(a.split()[0] in ev for a in aliases):
                sig.update(a.lower() for a in aliases)
        # Also add the literal event keywords
        tokens = re.split(r"[_\s]+", ev)
        for tok in tokens:
            if len(tok) > 3 and not tok.isdigit():
                sig.add(tok)

    # Device hints
    device = p.get("device", "")
    if isinstance(device, str):
        for kw in ("android", "iphone", "prepaid", "sim"):
            if kw in device.lower():
                sig.add(kw)

    # Drop trivial tokens
    sig = {s for s in sig if len(s) >= 3 and s not in {"none", "usd", "the", "and"}}
    return sorted(sig)


def load_corpus(archetype: str) -> str:
    """Concat narrative_text + title from all scraped files for archetype."""
    base = SCRAPE / archetype / "raw"
    parts: list[str] = []
    for jf in base.glob("seed_narratives*.jsonl"):
        with jf.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                parts.append(rec.get("title", "") or "")
                parts.append(rec.get("narrative_text", "") or "")
    return " ".join(parts).lower()


def score_archetype(archetype: str) -> dict:
    personas = json.loads(
        (V2 / archetype / "personas" / "persona_profiles.json").read_text(encoding="utf-8")
    )["personas"]
    corpus = load_corpus(archetype)

    per_persona = []
    for p in personas:
        signals = extract_persona_signals(p, archetype)
        if not signals:
            continue
        hits = [s for s in signals if s in corpus]
        per_persona.append({
            "persona_id": p["persona_id"],
            "name": p.get("name", ""),
            "n_signals": len(signals),
            "n_hits": len(hits),
            "pct": round(100.0 * len(hits) / len(signals), 1),
            "missing": [s for s in signals if s not in corpus][:8],
            "hit_examples": hits[:6],
        })

    total_signals = sum(r["n_signals"] for r in per_persona)
    total_hits = sum(r["n_hits"] for r in per_persona)
    return {
        "archetype": archetype,
        "n_personas": len(per_persona),
        "total_signals": total_signals,
        "total_hits": total_hits,
        "pct": round(100.0 * total_hits / total_signals, 1) if total_signals else 0.0,
        "per_persona": per_persona,
        "corpus_chars": len(corpus),
    }


def main():
    results = {}
    for arch in ("remittance", "gig_worker", "unbanked", "itin"):
        results[arch] = score_archetype(arch)

    print("=" * 78)
    print("PERSONA <-> SCRAPED CORPUS OVERLAP")
    print("=" * 78)
    print(f"{'Archetype':<14} {'Personas':>8} {'Signals':>8} {'Hits':>6} {'Pct':>6}  Corpus")
    grand_sig = grand_hit = 0
    for arch, r in results.items():
        print(f"{arch:<14} {r['n_personas']:>8} {r['total_signals']:>8} "
              f"{r['total_hits']:>6} {r['pct']:>5}%  {r['corpus_chars']:>8} chars")
        grand_sig += r["total_signals"]
        grand_hit += r["total_hits"]
    overall = round(100.0 * grand_hit / grand_sig, 1)
    print("-" * 78)
    print(f"{'OVERALL':<14} {'':>8} {grand_sig:>8} {grand_hit:>6} {overall:>5}%")

    print("\nPer-persona breakdown (top signals matched):")
    for arch, r in results.items():
        print(f"\n[{arch}]")
        for pp in r["per_persona"]:
            print(f"  {pp['persona_id']:<10} {pp['name']:<28} "
                  f"{pp['n_hits']:>2}/{pp['n_signals']:<2} ({pp['pct']:>5}%)  "
                  f"hits={pp['hit_examples']}")

    out = V2 / "persona_scrape_overlap.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()