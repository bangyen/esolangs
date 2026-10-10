"""List expired logs and unreferenced timing snapshots; delete only with --apply."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from pathlib import Path

_SNAPSHOT = re.compile(r".+\.json\.[0-9a-f]{64}\.json\Z")
_SKIP = {".git", ".venv", ".worktrees", ".cache", "__pycache__"}


def candidates(root: Path, days: float, now: float) -> list[Path]:
    """Keep every referenced snapshot; refuse pruning with unreadable sidecars."""
    if not math.isfinite(days) or days < 0:
        raise ValueError("days must be finite and non-negative")
    files = []
    referenced = set()
    for directory, directories, names in os.walk(root):
        directories[:] = [
            name
            for name in directories
            if name not in _SKIP and not (Path(directory) / name).is_symlink()
        ]
        for name in names:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            if name.endswith(".json.meta.json"):
                metadata = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(metadata, dict):
                    raise ValueError(f"{path}: invalid timing sidecar")
                snapshot = metadata.get("durations_file")
                if snapshot is not None:
                    if not isinstance(snapshot, str) or Path(snapshot).name != snapshot:
                        raise ValueError(f"{path}: invalid timing snapshot path")
                    referenced.add(path.parent / snapshot)
            if _SNAPSHOT.fullmatch(name) or (
                path.suffix == ".log"
                and path.parent
                in {root / "notes" / "benchmarks", root / "notes" / "verification"}
            ):
                files.append(path)
    cutoff = now - days * 86400
    return sorted(
        path
        for path in files
        if path not in referenced and path.stat().st_mtime < cutoff
    )


def main(argv: list[str] | None = None) -> int:
    """Preview expiration candidates, requiring --apply for deletion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--days", type=float, default=30)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        expired = candidates(args.root.resolve(), args.days, time.time())
        for path in expired:
            print(f"{'delete' if args.apply else 'would delete'} {path}")
        if args.apply:
            # Refresh references and ages before touching files selected by the preview.
            eligible = set(candidates(args.root.resolve(), args.days, time.time()))
            for path in expired:
                if path in eligible:
                    path.unlink()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
