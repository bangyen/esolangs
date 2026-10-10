"""Generate and execute artifacts in the supervised benchmark process."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import benchmark


def main() -> None:
    protocol = sys.stdout

    execution = 0

    def progress(phase: str) -> None:
        nonlocal execution
        message: dict[str, str | int] = {"phase": phase}
        if phase == "execution":
            message["index"] = execution
            execution += 1
        print(json.dumps(message), file=protocol, flush=True)

    for line in sys.stdin:
        execution = 0
        request = json.loads(line)
        token = benchmark._EVIDENCE.set(request["identity"])  # noqa: SLF001
        try:
            arguments = request["arguments"]
            timeout = arguments["timeout"]
            arguments["timeout"] = None
            with contextlib.redirect_stdout(sys.stderr):
                result = benchmark._measure(**arguments, _progress=progress)  # noqa: SLF001
            result["timeout"] = timeout
            message = {"result": result}
        except Exception as error:
            message = {"error": {"type": type(error).__name__, "message": str(error)}}
        finally:
            benchmark._EVIDENCE.reset(token)  # noqa: SLF001
        print(json.dumps(message), file=protocol, flush=True)


if __name__ == "__main__":
    main()
