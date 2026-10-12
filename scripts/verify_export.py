#!/usr/bin/env python3
"""Verify an exported AgentFault dataset against its manifest.

Recomputes every file's SHA-256 and record count, and re-derives the content
hash, reporting any mismatch. Exits non-zero on failure so it can gate a
release CI job.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.export_dataset import file_sha256


def verify_export(out_dir: str | Path) -> list[str]:
    out_dir = Path(out_dir)
    manifest_path = out_dir / "manifest.json"

    if not manifest_path.is_file():
        return [f"missing manifest: {manifest_path}"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    for name, meta in manifest.get("files", {}).items():
        path = out_dir / name

        if not path.is_file():
            errors.append(f"missing file: {name}")
            continue

        actual_sha = file_sha256(path)

        if actual_sha != meta.get("sha256"):
            errors.append(
                f"{name}: sha256 mismatch "
                f"(manifest {meta.get('sha256')[:12]}…, actual {actual_sha[:12]}…)"
            )

        with open(path, "rb") as f:
            records = sum(1 for line in f if line.strip())

        if records != meta.get("records"):
            errors.append(
                f"{name}: record count {records} != manifest {meta.get('records')}"
            )

    baseline = out_dir / "baseline.jsonl"
    injected = out_dir / "injected.jsonl"

    if baseline.is_file() and injected.is_file():
        digest = hashlib.sha256()
        digest.update(baseline.read_bytes())
        digest.update(injected.read_bytes())
        content_hash = digest.hexdigest()

        if content_hash != manifest.get("content_hash"):
            errors.append(
                f"content_hash mismatch "
                f"(manifest {manifest.get('content_hash')}, actual {content_hash})"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "out", nargs="?", type=Path, default=Path("dataset/agentfault-500")
    )
    args = parser.parse_args()

    errors = verify_export(args.out)

    if errors:
        print(f"FAIL: {len(errors)} problem(s) in {args.out}")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"OK: {args.out} matches its manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
