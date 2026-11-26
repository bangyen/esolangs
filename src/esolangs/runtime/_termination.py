"""Observe IO while proving halting or a repeated machine state."""

from collections.abc import Callable
from dataclasses import replace
from functools import partial
from typing import cast

import esolangs.runtime._execution as _execution_runtime
from esolangs._cycles import _DrawDependentHaltError, _halt_or_cycle_result, _unwrap
from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.exceptions import (
    EsolangError,
    ExecutionTimeoutError,
    InterpreterLimitError,
    steps_exhausted,
)
from esolangs.registry._catalog import Catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._branch_search import (
    _BranchingUnavailableError,
    _ProofBudgetExhaustedError,
    _ProofSnapshotUnavailableError,
)
from esolangs.runtime._drive import _check_snapshot_hash
from esolangs.runtime._input import InputSource
from esolangs.runtime._prepared import _PreparedRuntime
from esolangs.runtime._program import Program
from esolangs.runtime._proof import (
    BranchProof,
    TerminationResult,
    checked_decision,
    checked_termination,
)
from esolangs.runtime._proof_runtime import _branch_snapshot
from esolangs.runtime._vm_adapter import _capture_observation, _record_vm_fault
from esolangs.runtime._vm_protocol import VM, _BranchingStepMachine
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options
from esolangs.vm import _make_vm


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
    state = _branch_snapshot(branch, machine)
    seen = set()
    if state != proof.root:
        _check_snapshot_hash(state, InterpreterLimitError)
        raise InterpreterLimitError("branch observation does not start at its root")
    while True:
        try:
            if state not in graph or state in seen:
                break
            seen.add(state)
        except TypeError:
            _check_snapshot_hash(state, InterpreterLimitError)
            raise
        if machine.halted:
            raise InterpreterLimitError(
                "live machine halted before branch evidence ends"
            )
        machine.step()
        successor = _branch_snapshot(branch, machine)
        if successor not in graph[state]:
            _check_snapshot_hash(successor, InterpreterLimitError)
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
    *,
    max_steps: int | None = None,
    settings: DialectSettings | None = None,
    catalog: "Catalog | None" = None,
    io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    prepared: _PreparedRuntime | None = None,
) -> TerminationResult:
    """Retain live IO and proof evidence without taking a post-halt dump step."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(name)
    random = catalog.languages[name].runtime.random
    if prepared is None:
        dialect_options(name, settings, catalog=catalog)

    def _drive(*_args: object) -> TerminationResult:
        factory = partial(
            _make_vm,
            settings=settings,
            catalog=catalog,
            io_factory=io_factory,
        )
        machine = factory(name, source, stdin=stdin, prepared=prepared)
        steps: int | None = None

        def record_commands(count: int) -> None:
            nonlocal steps
            steps = count

        def observe() -> ExecutionResult:
            return replace(_capture_observation(machine), steps=steps)

        try:
            try:
                decision = _halt_or_cycle_result(
                    machine,
                    max_steps,
                    require_branches=random,
                    record_commands=record_commands if max_steps is not None else None,
                )
            except ExecutionTimeoutError:
                raise
            except (
                _BranchingUnavailableError,
                _DrawDependentHaltError,
                _ProofSnapshotUnavailableError,
                TimeoutError,
            ) as error:
                if (
                    isinstance(error, _ProofBudgetExhaustedError)
                    and max_steps is not None
                ):
                    raise steps_exhausted(str(error)) from error
                failure = InterpreterLimitError(str(error))
                for note in getattr(error, "__notes__", ()):
                    failure.add_note(note)
                raise failure from error
            try:
                checked_decision(decision)
            except ValueError:
                return TerminationResult(observe(), decision)
            if decision.branches is not None:
                _observe_branch_path(machine, decision.branches)
            return TerminationResult(observe(), decision)
        except EsolangError as error:
            if error.observation is None or steps is not None:
                _record_vm_fault(machine, error, observe())
            raise

    argument = (
        source.source
        if isinstance(source, (ProgramArtifact, TemplateArtifact))
        else source
    )
    verdict = _execution_runtime.invoke(_drive, argument, ScriptedIO(""))
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
            failure.observation = replace(verdict.observation, completion=None)
            failure.partial_output = failure.observation.output
        raise failure from error
