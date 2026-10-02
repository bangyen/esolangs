"""Execute in a disposable interpreter with a portable wall-clock deadline."""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 -- fixed Python worker; source travels over stdin.
import sys
from threading import Thread
from time import monotonic
from typing import Any, cast

from esolangs import exceptions
from esolangs._source import InputSource, ProgramSource, read_input
from esolangs._validate import check_timeout
from esolangs.raster import Raster
from esolangs.registry import resolve


def _decode(text: str, *, expired: bool) -> str:
    error: exceptions.EsolangError
    output: list[str] = []
    result: dict[str, Any] | None = None
    for line in text.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            break  # A killed write may leave only part of its last JSON record.
        if "output" in message:
            output.append(message["output"])
        else:
            result = message
    partial = "".join(output)
    if expired:
        error = exceptions.ExecutionTimeoutError(
            "isolated execution exceeded its deadline"
        )
        error.partial_output = partial
        raise error
    if result is None:
        error = exceptions.InterpreterLimitError(
            "isolated interpreter exited without a result"
        )
        error.partial_output = partial
        raise error
    if "error" in result:
        kind = result["error"]
        cls = getattr(exceptions, kind, exceptions.InterpreterLimitError)
        args = result["args"]
        if kind == "UnknownLanguageError":
            args = [args[0], tuple(args[1])]
        error = cls(*args)
        error.partial_output = partial
        for note in result.get("notes", []):
            error.add_note(note)
        raise error
    return cast("str", result["result"])


def run_isolated(
    language: str,
    program: ProgramSource,
    stdin: InputSource = "",
    timeout: float = 30.0,
    *,
    seed: int | None = None,
    scale: int | None = None,
) -> str:
    """Return output from a subprocess; the deadline includes loading and startup.

    Works on Windows and worker threads. Errors retain their public class,
    notes and output; timeout kills and reaps the child.
    A blocked caller-owned stream read may finish in the background after timeout.
    """
    import esolangs

    check_timeout(timeout)
    if timeout is None:
        raise exceptions.ArgumentError("isolated execution requires a finite timeout")
    name = resolve(language)
    deadline = monotonic() + timeout
    box: list[str | BaseException] = []

    def prepare() -> None:
        try:
            source = esolangs.check_program(name, program, stdin)
            box.append(
                json.dumps(
                    {
                        "language": name,
                        "program": source.rows
                        if isinstance(source, Raster)
                        else source,
                        "raster": isinstance(source, Raster),
                        "stdin": read_input(stdin),
                        "seed": seed,
                        "scale": scale,
                    }
                )
            )
        except BaseException as exc:
            box.append(exc)

    # Caller-owned streams need not be picklable or interruptible. A daemon
    # bounds acquisition without transferring or closing their handles.
    reader = Thread(target=prepare, daemon=True)
    reader.start()
    reader.join(max(0.0, deadline - monotonic()))
    remaining = deadline - monotonic()
    if reader.is_alive() or remaining <= 0:
        raise exceptions.ExecutionTimeoutError(
            "execution timed out while loading input"
        )
    request = box[0]
    if isinstance(request, BaseException):
        raise request
    return _launch(request, remaining)


def _launch(request: str, timeout: float) -> str:
    """Run one JSON request, killing and reaping on deadline."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    with subprocess.Popen(  # nosec B603 -- fixed executable and code, no shell.
        [sys.executable, "-c", "from esolangs._isolated import _worker; _worker()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    ) as child:
        expired = False
        try:
            output, _stderr = child.communicate(request, timeout=timeout)
        except subprocess.TimeoutExpired:
            expired = True
            child.kill()
            output, _stderr = child.communicate()
        except BaseException:
            child.kill()
            child.communicate()
            raise
    return _decode(output, expired=expired)


def termination_isolated(
    name: str,
    source: str,
    stdin: str,
    timeout: float,
    halts: str,
    diverges: str,
) -> str:
    """Prove halt or cycle in a child; deadline never means divergence."""
    return _launch(
        json.dumps(
            {
                "language": name,
                "program": source,
                "stdin": stdin,
                "raster": False,
                "termination": [halts, diverges],
            }
        ),
        timeout,
    )


def _worker() -> None:
    """Stream output and a structured verdict to the parent."""
    import esolangs
    from esolangs.interpreters.io import ScriptedIO

    def send(message: dict[str, Any]) -> None:
        print(json.dumps(message), flush=True)

    class StreamingIO(ScriptedIO):
        def _write(self, value: object) -> None:
            super()._write(value)
            send({"output": str(value)})

    vars(esolangs)["ScriptedIO"] = StreamingIO
    request = json.load(sys.stdin)
    program = request["program"]
    if request["raster"]:
        program = Raster(tuple(tuple(tuple(pixel) for pixel in row) for row in program))
    try:
        if "termination" in request:
            from esolangs._evaluate import _terminates

            halts, diverges = request["termination"]
            output = _terminates(
                request["language"], program, request["stdin"], None, halts, diverges
            )
        else:
            output = esolangs.run(
                request["language"],
                program,
                request["stdin"],
                timeout=None,
                seed=request["seed"],
                scale=request.get("scale"),
            )
    except exceptions.EsolangError as error:
        args: tuple[object, ...] = error.args
        if isinstance(error, exceptions.UnknownLanguageError):
            args = (error.language, error.suggestions)
        elif isinstance(error, exceptions.InputExhaustedError):
            args = (error.reads, error.supplied)
        send(
            {
                "error": type(error).__name__,
                "args": args,
                "notes": getattr(error, "__notes__", []),
            }
        )
    else:
        send({"result": output})


if __name__ == "__main__":
    _worker()
