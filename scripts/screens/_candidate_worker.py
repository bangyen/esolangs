"""Generate and execute both candidate artifacts under supervision."""

import contextlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candidate
from _build import source_size
from benchmark import _execute, artifact_hash

import esolangs
from esolangs.raster import Raster


def main() -> None:
    """Emit ordered phases and actual baseline/candidate execution results."""
    protocol = sys.stdout
    request = json.loads(sys.stdin.readline())["arguments"]
    try:
        print(json.dumps({"phase": "generation"}), file=protocol, flush=True)
        with contextlib.redirect_stdout(sys.stderr):
            old = esolangs.generate(request["language"], request["table"])
            fn = candidate._load(request["candidate"])  # noqa: SLF001
            with candidate._patched(request["language"], request["target"], fn):  # noqa: SLF001
                new = esolangs.generate(request["language"], request["table"])
        result: dict[str, Any] = {
            "size_unit": "cells"
            if isinstance(old, Raster)
            or esolangs.describe(request["language"])["state_model"] == "grid"
            else "characters",
            "old_size": source_size(request["language"], old),
            "new_size": source_size(request["language"], new),
            "old_artifact_sha256": artifact_hash(old),
            "new_artifact_sha256": artifact_hash(new),
        }
        index = 0
        for name, program in (("new", new), ("old", old)):
            executions = []
            for row in request["rows"]:
                print(
                    json.dumps({"phase": "execution", "index": index}),
                    file=protocol,
                    flush=True,
                )
                index += 1
                with contextlib.redirect_stdout(sys.stderr):
                    executions.append(
                        _execute(
                            request["language"],
                            program,
                            request["table"],
                            row,
                            request["step_cap"],
                            None,
                        )
                    )
            result[name + "_executions"] = executions
        message = {"result": result}
    except Exception as error:
        message = {"error": {"type": type(error).__name__, "message": str(error)}}
    print(json.dumps(message), file=protocol, flush=True)


if __name__ == "__main__":
    main()
