"""Observe IO while proving halting or a repeated machine state."""

from collections.abc import Callable
from functools import partial
from typing import cast

import esolangs.runtime._execution as _execution_runtime
from esolangs._cycles import _BranchingStepMachine, _halt_or_cycle_result, _unwrap
from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.exceptions import (
    EsolangError,
    ExecutionTimeoutError,
    InterpreterLimitError,
)
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._input import InputSource
from esolangs.runtime._prepared import PreparedProgram
from esolangs.runtime._program import Program
from esolangs.runtime._proof import (
    BranchProof,
    TerminationResult,
    checked_decision,
    checked_termination,
)
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options
from esolangs.vm import VM, _capture_observation, _make_vm


def _observe_branch_path(machine: VM, proof: BranchProof) -> None:
    """Retain live IO along a proved path, checking every transition."""
    # Branch exploration discards output effects: Fish's '"A"o;' proves a
    # halt without printing. Observe a real path before capturing its IO.
    branch = cast(
        _BranchingStepMachine,
        _unwrap(
            machine,
            _BranchingStepMachine,
            "branch-enumerable",
            hint="observe the machine that supplied the branching evidence",
        ),
    )
    graph = dict(proof.transitions)
    state = branch.branching_snapshot()
    seen = set()
    if state != proof.root:
        raise InterpreterLimitError("branch observation does not start at its root")
    while state in graph and state not in seen:
        seen.add(state)
        machine.step()
        successor = branch.branching_snapshot()
        if successor not in graph[state]:
            raise InterpreterLimitError(
                "live transition is absent from branch evidence"
            )
        state = successor
    if machine.halted is not proof.halts or (
        state != proof.terminal if proof.halts else state not in seen
    ):
        raise InterpreterLimitError("live endpoint disagrees with branch evidence")


def _termination_result(
    name: str,
    source: Program | Artifact,
    stdin: str,
    bound: float | None,
    *,
    max_steps: int | None = None,
    settings: DialectSettings | None = None,
    catalog: "Catalog | None" = None,
    io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    prepared: PreparedProgram | None = None,
) -> TerminationResult:
    """Retain live IO and proof evidence without taking a post-halt dump step."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if prepared is None:
        dialect_options(name, settings, catalog=catalog)

    def _drive(*_args: object) -> TerminationResult:
        factory = partial(
            _make_vm, settings=settings, catalog=catalog, io_factory=io_factory
        )
        machine = factory(name, source, stdin=stdin, prepared=prepared)
        try:
            try:
                decision = (
                    _halt_or_cycle_result(machine)
                    if max_steps is None
                    else _halt_or_cycle_result(machine, max_steps)
                )
            except ExecutionTimeoutError:
                raise
            except TimeoutError as error:
                failure = ExecutionTimeoutError(str(error))
                failure.bound = "max_steps"
                raise failure from error
            try:
                checked_decision(decision)
            except ValueError:
                return TerminationResult(_capture_observation(machine), decision)
            if decision.branches is not None:
                _observe_branch_path(machine, decision.branches)
            return TerminationResult(_capture_observation(machine), decision)
        except EsolangError as error:
            if error.execution is None:
                error.execution = _capture_observation(machine)
            error.partial_output = error.execution.output
            raise

    argument = (
        source.source
        if isinstance(source, (ProgramArtifact, TemplateArtifact))
        else source
    )
    verdict = _execution_runtime.run_guard(_drive, argument, ScriptedIO(""), bound)
    try:
        return checked_termination(verdict)
    except ValueError as error:
        failure = InterpreterLimitError(
            "termination driver returned no decision evidence",
            hint="check the termination driver or report this interpreter error",
        )
        if isinstance(verdict, TerminationResult) and isinstance(
            verdict.observation, ExecutionResult
        ):
            failure.execution = verdict.observation._replace(completion=None)
            failure.partial_output = failure.execution.output
        raise failure from error
