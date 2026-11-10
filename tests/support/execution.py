"""Observe outcomes through a raising adapter with caller-supplied test IO."""

from typing import Any

from esolangs.operations.execution import _execute_invocation
from esolangs.results import ExecutionResult
from esolangs.runtime._source import ProgramSource


def run_observed(
    language: str, program: ProgramSource, **options: Any
) -> ExecutionResult:
    return _execute_invocation(language, program, **options).unwrap()
