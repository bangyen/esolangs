"""Run declared raw-program checks in fresh processes, clean and with a fault."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from esolangs.registry import LANGUAGES
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime.io import IO, ScriptedIO


class Results:
    """Count executed assertions separately from collection and fixture failures."""

    def __init__(self) -> None:
        """Start all execution counters at zero."""
        self.passed = self.assertions = self.other = self.calls = self.hits = 0

    def pytest_runtest_makereport(self, item: Any, call: Any) -> None:
        """Record call assertions without accepting setup or collection errors."""
        del item
        if call.when == "call":
            self.calls += 1
            if call.excinfo is None:
                self.passed += 1
            elif call.excinfo.errisinstance(AssertionError):
                self.assertions += 1
            else:
                self.other += 1
        elif call.excinfo is not None:
            self.other += 1


def inject(name: str, result: Results) -> None:
    """Add an unwanted output byte at both native and stepped entry points."""
    # Import by name so mypy does not duplicate its script module root.
    trace_driver = importlib.import_module("scripts.tracediff")

    lang = LANGUAGES[name]
    module = interpreter_module(lang.name)
    samples = importlib.import_module("tests.support.samples").SAMPLES
    source, stdin = samples[lang.name]
    representative = trace_driver._machine(  # noqa: SLF001 -- owned trace binder
        module, source, ScriptedIO(stdin), runtime=lang.runtime
    )
    # The factory identifies the implementation; native oracles stay independent.
    target: Any = type(representative)
    original = target.__init__

    def corrupt(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        for value in (*args, *kwargs.values()):
            if isinstance(value, IO):
                value.print_str("\x00")
                result.hits += 1
                return

    def broken(self: Any, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        corrupt(args, kwargs)

    target.__init__ = broken
    entry = lang.runtime.completion_entrypoint
    execute = getattr(module, entry)

    def native(*args: Any, **kwargs: Any) -> Any:
        corrupt(args, kwargs)
        return execute(*args, **kwargs)

    setattr(module, entry, native)


def check(request: dict[str, Any], *, fault: bool) -> dict[str, Any]:
    """Return one run's report; retain pytest diagnostics on failure."""
    result = Results()
    if fault:
        inject(request["language"], result)
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        status = pytest.main(
            [
                "-o",
                "addopts=",
                "-o",
                "python_functions=test_* check_raw_*"
                if request["kind"] == "model"
                else "python_functions=test_*",
                "-q",
                "--tb=short",
                # Expected trace mismatches took >30s in Python 3.12 difflib.
                "--assert=plain",
                *(["-x"] if fault else []),
                *request["tests"],
            ],
            plugins=[result],
        )
    return {"status": int(status), **vars(result), "log": captured.getvalue()}


def main() -> None:
    """Emit one report per requested run, each from a fork before test imports.

    The fault must be injected before the declared tests import the
    interpreter, so the runs cannot share a process; forking after the
    package and pytest imports saves a process start and those imports per
    run (test_semantic_evidence on four workers: 35.2 s -> 26.7 s).
    """
    request = json.load(sys.stdin)
    reports = []
    for fault in request["faults"]:
        read, write = os.pipe()
        pid = os.fork()
        if pid == 0:  # pragma: no cover - the child reports through the pipe
            os.close(read)
            try:
                payload = check(request, fault=fault)
            except BaseException as error:
                payload = {"status": -1, "log": repr(error)}
            with os.fdopen(write, "w") as output:
                output.write(json.dumps(payload))
            os._exit(0)
        os.close(write)
        with os.fdopen(read) as received:
            text = received.read()
        os.waitpid(pid, 0)
        reports.append(json.loads(text))
    print(json.dumps(reports))


if __name__ == "__main__":
    main()
