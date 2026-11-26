"""Run declared raw-program checks in fresh processes, clean and with a fault."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from esolangs.registry import LANGUAGES
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime.io import IO


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
    lang = LANGUAGES[name]
    module = interpreter_module(lang.name)
    target = module._Machine  # noqa: SLF001 - interpreter's declared machine
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
    if entry is None:
        hook = lang.runtime.machine_preparation
        prepare = getattr(module, hook)

        def faulty_plan(*args: Any, **kwargs: Any) -> Any:
            plan = prepare(*args, **kwargs)

            def run(port: IO) -> Any:
                corrupt((port,), {})
                return plan.run(port)

            return replace(plan, run=run)

        setattr(module, hook, faulty_plan)
        return
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
