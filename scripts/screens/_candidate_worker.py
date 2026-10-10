"""Generate and execute both candidate artifacts under supervision."""

import contextlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candidate
from _atomic import write_text
from _build import source_measurement
from _candidate_evidence import dependencies_changed, loaded_dependencies
from benchmark import _execute, artifact_hash

import esolangs


def main() -> None:
    """Emit ordered phases and actual baseline/candidate execution results."""
    protocol = sys.stdout
    request = json.loads(sys.stdin.readline())["arguments"]
    dependencies: dict[str, str] = {}
    try:
        print(json.dumps({"phase": "generation"}), file=protocol, flush=True)
        with contextlib.redirect_stdout(sys.stderr):
            old = esolangs.generate(request["language"], request["table"])
            fn = candidate._load(request["candidate"])  # noqa: SLF001
            dependencies = loaded_dependencies(request["candidate"])
            if request.get("dependency_report"):
                write_text(Path(request["dependency_report"]), json.dumps(dependencies))
            with candidate._patched(request["language"], request["target"], fn):  # noqa: SLF001
                new = esolangs.generate(request["language"], request["table"])
        old_source = source_measurement(request["language"], old)
        new_source = source_measurement(request["language"], new)
        if old_source["unit"] != new_source["unit"]:
            raise ValueError("candidate source measurement units changed")
        result: dict[str, Any] = {
            "size_unit": old_source["unit"],
            "old_source": old_source,
            "new_source": new_source,
            "old_size": old_source["size"],
            "new_size": new_source["size"],
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
        if dependencies_changed(dependencies):
            raise RuntimeError("candidate dependencies changed during execution")
        message = {"result": result}
    except Exception as error:
        message = {"error": {"type": type(error).__name__, "message": str(error)}}
    for name, digest in loaded_dependencies(request["candidate"]).items():
        dependencies.setdefault(name, digest)
    if request.get("dependency_report"):
        write_text(
            Path(request["dependency_report"]),
            json.dumps(dependencies),
        )
    print(json.dumps(message), file=protocol, flush=True)


if __name__ == "__main__":
    main()
