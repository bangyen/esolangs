"""Require complete, disjoint shard selection and successful execution evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pytest_shard import collect_ids
from refresh_ci_timings import load_run


def check(paths: list[Path], corpus: list[str], marker: str, shards: int) -> None:
    """Check all shard manifests and completion sidecars against fresh collection."""
    if shards < 1:
        raise ValueError("shards must be positive")
    expected = set(corpus)
    selected: set[str] = set()
    executed: set[str] = set()
    indices: set[int] = set()
    identity = None
    excluded = None
    if len(paths) != shards:
        raise ValueError("missing or extra shard manifests")
    for path in paths:
        record = json.loads(path.read_text())
        if (
            not isinstance(record, dict)
            or record.get("schema") != 1
            or record.get("marker") != marker
            or record.get("shards") != shards
        ):
            raise ValueError(f"{path}: incompatible shard manifest")
        index = record.get("shard")
        if type(index) is not int or not 0 <= index < shards or index in indices:
            raise ValueError("duplicate or invalid shard index")
        indices.add(index)
        for key in ("collected", "selected", "excluded"):
            nodes = record.get(key)
            if (
                not isinstance(nodes, list)
                or not all(isinstance(node, str) for node in nodes)
                or len(nodes) != len(set(nodes))
            ):
                raise ValueError(f"{path}: invalid {key} nodes")
        if set(record["collected"]) != expected:
            raise ValueError("shard collection differs from current corpus")
        run = record.get("run")
        if not isinstance(run, dict) or (identity is not None and run != identity):
            raise ValueError("mixed shard run identities")
        identity = run
        omissions = set(record["excluded"])
        if not omissions <= expected or (
            excluded is not None and omissions != excluded
        ):
            raise ValueError("incompatible shard exclusions")
        excluded = omissions
        nodes = set(record["selected"])
        if not nodes <= expected - omissions or nodes & selected:
            raise ValueError("overlapping or unexpected shard selection")
        selected.update(nodes)
        actual = set()
        for sidecar in path.parent.rglob("*.json.meta.json"):
            metadata = json.loads(sidecar.read_text())
            if (
                not isinstance(metadata, dict)
                or not isinstance(metadata.get("collected"), list)
                or any(
                    metadata.get("run", {}).get(key) != value
                    for key, value in run.items()
                )
            ):
                raise ValueError("missing or mixed execution identity")
            actual.update(metadata["collected"])
        if not nodes <= actual or not actual <= nodes | omissions or actual & executed:
            raise ValueError("missing, overlapping, or unexpected executed tests")
        if actual:
            load_run(path.parent, actual)
        elif nodes:
            raise ValueError("missing completion evidence")
        executed.update(actual)
    if selected != expected - (excluded or set()) or executed != expected:
        raise ValueError("shards omit collected tests")


def main(argv: list[str] | None = None) -> int:
    """Inspect downloaded manifests, recollecting the requested test band."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--shards", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        check(
            sorted(args.directory.rglob("*.shard.json")),
            collect_ids(args.marker),
            args.marker,
            args.shards,
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print("all shards selected and completed the collected corpus exactly once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
