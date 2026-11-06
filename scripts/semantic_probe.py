"""Run declared raw-program checks in a fresh process, optionally injecting a fault."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
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


def main() -> None:
    """Emit one machine-readable report; retain pytest diagnostics on failure."""
    request = json.load(sys.stdin)
    result = Results()
    if request["fault"]:
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
                *(["-x"] if request["fault"] else []),
                *request["tests"],
            ],
            plugins=[result],
        )
    print(
        json.dumps({"status": int(status), **vars(result), "log": captured.getvalue()})
    )


if __name__ == "__main__":
    main()
