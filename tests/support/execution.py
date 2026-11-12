"""Observe outcomes through a raising adapter with caller-supplied test IO."""

from typing import Any

from esolangs.operations.execution import _execute_invocation
from esolangs.results import ExecutionResult
from esolangs.runtime._execution import run_guard
from esolangs.runtime._source import ProgramSource
from esolangs.runtime.io import ScriptedIO


def run_observed(
    language: str, program: ProgramSource, **options: Any
) -> ExecutionResult:
    timeout = options.pop("timeout", None)
    if options.get("isolated"):
        return _execute_invocation(
            language, program, timeout=timeout, **options
        ).unwrap()
    return run_guard(
        lambda *_args: _execute_invocation(language, program, **options).unwrap(),
        "",
        ScriptedIO(""),
        timeout,
    )
