"""Compute mean coherence per archetype from each round's adapted_output_round*.jsonl."""
import json, re
from pathlib import Path

V2 = Path(__file__).resolve().parents[2] / "datasets_v2"

def extract_score(text: str):
    if not text: return None
    m = re.search(r'"coherence_score"\s*:\s*([0-9.]+)', text)
    if m: return float(m.group(1))
    m = re.search(r'coherence[^\d]{0,20}([01](?:\.\d+)?)', text)
    return float(m.group(1)) if m else None

def mean_for(path: Path):
    scores = []
    if not path.exists(): return None, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try: rec = json.loads(line)
        except: continue
        txt = rec.get("enhanced_completion") or rec.get("completion") or rec.get("output") or ""
        if isinstance(txt, dict): txt = json.dumps(txt)
        s = extract_score(txt)
        if s is not None: scores.append(s)
    return (sum(scores)/len(scores) if scores else None), len(scores)

for arch in ("remittance","gig_worker","unbanked","itin"):
    print(f"\n[{arch}]")
    for rnd in (1,2,3,4):
        p = V2/arch/"persona_verification"/f"adapted_output_round{rnd}.jsonl"
        m, n = mean_for(p)
        print(f"  round{rnd}: mean={m!r} n={n}")