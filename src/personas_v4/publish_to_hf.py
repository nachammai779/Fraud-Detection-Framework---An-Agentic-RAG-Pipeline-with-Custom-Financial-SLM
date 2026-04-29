"""
Publish the v4 dataset to Hugging Face Hub as two repos:

  Nachammai41/underserved-persona_conditioned-fraud-v4
      README.md + 8 configs (all + 4 archetypes + personas + sources + typology_registry)

  Nachammai41/underserved-persona_conditioned-fraud-v4-cot
      README.md + 1 config (cot_reasoning, the CoT traces)

Stages each repo's tree under datasets_v4/_publish_staging/{main,cot}/
then uploads via huggingface_hub.HfApi.

Usage:
  python src/personas_v4/publish_to_hf.py --main      # main repo only
  python src/personas_v4/publish_to_hf.py --cot       # cot repo only
  python src/personas_v4/publish_to_hf.py --both      # both
  python src/personas_v4/publish_to_hf.py --dry-run   # stage but skip upload
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"
HF_DATA = V4 / "huggingface" / "data"
STAGING = V4 / "_publish_staging"

MAIN_REPO = "Nachammai41/underserved-persona_conditioned-fraud-v4"
COT_REPO = "Nachammai41/underserved-persona_conditioned-fraud-v4-cot"

MAIN_CONFIGS = ["all", "remittance", "gig_worker", "unbanked", "itin",
                "personas", "sources", "typology_registry"]


def _stage_main() -> Path:
    out = STAGING / "main"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy(V4 / "huggingface" / "README.md", out / "README.md")
    for cfg in MAIN_CONFIGS:
        src = HF_DATA / cfg / "train.parquet"
        if not src.exists():
            raise SystemExit(f"missing {src} — run build_hf_data.py first")
        dst_dir = out / "data" / cfg
        dst_dir.mkdir(parents=True)
        shutil.copy(src, dst_dir / "train.parquet")
    return out


def _stage_cot() -> Path:
    out = STAGING / "cot"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy(V4 / "huggingface" / "README_cot.md", out / "README.md")
    src = HF_DATA / "cot_reasoning" / "train.parquet"
    if not src.exists():
        raise SystemExit(f"missing {src} — run build_hf_data.py first")
    dst_dir = out / "data"
    dst_dir.mkdir(parents=True)
    shutil.copy(src, dst_dir / "train.parquet")
    return out


def _summarize(path: Path):
    files = sorted(path.rglob("*"))
    total = 0
    print(f"  staging: {path}")
    for f in files:
        if f.is_file():
            sz = f.stat().st_size
            total += sz
            print(f"    {f.relative_to(path)}  ({sz/1e6:.2f} MB)")
    print(f"  total: {total/1e6:.2f} MB")


def _upload(repo_id: str, folder: Path):
    from huggingface_hub import HfApi
    api = HfApi()
    print(f"\nuploading -> {repo_id}")
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True, private=False)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(folder),
        commit_message="Initial publish: v4 + v4.1 dataset (25/25 typology coverage)",
    )
    print(f"  done: https://huggingface.co/datasets/{repo_id}")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--main", action="store_true")
    g.add_argument("--cot", action="store_true")
    g.add_argument("--both", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    do_main = args.main or args.both
    do_cot = args.cot or args.both

    if do_main:
        print("=== main repo ===")
        p = _stage_main()
        _summarize(p)
        if not args.dry_run:
            _upload(MAIN_REPO, p)

    if do_cot:
        print("\n=== cot repo ===")
        p = _stage_cot()
        _summarize(p)
        if not args.dry_run:
            _upload(COT_REPO, p)

    if args.dry_run:
        print("\n[dry-run] no uploads performed.")


if __name__ == "__main__":
    main()