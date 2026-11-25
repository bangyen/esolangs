"""Require complete, disjoint shard selection and successful execution evidence."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci.shard import (
    CollectionError,
    collect_ids,
    load_run,
    read_completion_metadata,
    read_evidence_json,
)


def _check_completion_identity(
    sidecar: Path, completion: dict[str, object], manifest: Path, run: dict[str, object]
) -> None:
    python = f"{sys.version_info.major}.{sys.version_info.minor}"
    version = completion.get("python")
    if not isinstance(version, str) or not version.startswith(f"{python}."):
        raise ValueError(
            f"{sidecar}: completion Python {version!r} does not match "
            f"the verifier's Python {python}"
        )
    if any(completion.get(key) != value for key, value in run.items()):
        raise ValueError(f"{sidecar}: completion field 'run' differs from {manifest}")


def check(paths: list[Path], corpus: list[str], marker: str, shards: int) -> None:
    """Check all shard manifests and completion sidecars against fresh collection."""
    if shards < 1:
        raise ValueError("shards must be positive")
    expected = set(corpus)
    current_run = {
        key: value
        for key, variable in (("id", "GITHUB_RUN_ID"), ("commit", "GITHUB_SHA"))
        if (value := os.environ.get(variable))
    }
    selected: set[str] = set()
    executed: set[str] = set()
    indices: set[int] = set()
    identity = None
    excluded = None
    if len(paths) != shards:
        raise ValueError("missing or extra shard manifests")
    for path in paths:
        record = read_evidence_json(path, kind="shard manifest")
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
        if not isinstance(run, dict):
            raise ValueError(f"{path}: invalid shard field 'run': expected an object")
        if identity is not None and run != identity:
            raise ValueError("mixed shard run identities")
        for key, value in current_run.items():
            if run.get(key) != value:
                raise ValueError(
                    f"{path}: shard run {key} {run.get(key)!r} differs from "
                    f"the active CI run ({value!r})"
                )
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
        sidecars = {
            sidecar: read_completion_metadata(sidecar)
            for sidecar in sorted(path.parent.rglob("*.json.meta.json"))
        }
        for sidecar, metadata in sidecars.items():
            _check_completion_identity(sidecar, metadata["run"], path, run)
            actual.update(metadata["collected"])
        if not nodes <= actual or not actual <= nodes | omissions or actual & executed:
            raise ValueError("missing, overlapping, or unexpected executed tests")
        if sidecars:
            load_run(path.parent, actual, sidecars=sidecars)
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
    except (CollectionError, ValueError, OSError) as error:
        parser.error(str(error))
    print("all shards selected and completed the collected corpus exactly once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
