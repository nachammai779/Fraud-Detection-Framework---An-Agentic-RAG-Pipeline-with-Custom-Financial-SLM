"""Dump the full status + evaluation objects for both failed jobs."""
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from adaption import Adaption

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"

META_PATHS = [
    V4 / "v4_1" / "run_metadata.json",
    V4 / "reasoning" / "run_metadata.json",
]


def _dump(label, obj):
    print(f"  {label}:")
    if obj is None:
        print("    <none>")
        return
    # Try JSON first, then dict, then attribute walk
    try:
        print(json.dumps(obj, default=lambda o: getattr(o, "__dict__", str(o)),
                         indent=4, ensure_ascii=False))
    except Exception:
        for attr in dir(obj):
            if attr.startswith("_"):
                continue
            try:
                v = getattr(obj, attr)
            except Exception:
                continue
            if callable(v):
                continue
            print(f"    {attr}: {v!r}")


def main():
    key = os.environ.get("ADAPTION_API_KEY")
    if not key:
        raise SystemExit("ADAPTION_API_KEY not set")
    c = Adaption(api_key=key)

    for p in META_PATHS:
        print(f"\n===== {p} =====")
        if not p.exists():
            print("  (no metadata — job never submitted from this wrapper)")
            continue
        meta = json.loads(p.read_text(encoding="utf-8"))
        did = meta.get("dataset_id")
        print(f"  dataset_id: {did}")
        print(f"  run_id:     {meta.get('run_id')}")

        try:
            st = c.datasets.get_status(did)
        except Exception as e:
            print(f"  get_status raised: {e!r}")
            st = None
        _dump("status", st)

        try:
            ev = c.datasets.get_evaluation(did)
        except Exception as e:
            print(f"  get_evaluation raised: {e!r}")
            ev = None
        _dump("evaluation", ev)


if __name__ == "__main__":
    main()