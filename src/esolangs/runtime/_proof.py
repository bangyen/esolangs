"""Exact-state termination evidence, separate from output finalization."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, fields
from reprlib import recursive_repr
from typing import TYPE_CHECKING, NamedTuple, cast

from esolangs.exceptions import EsolangError, ExecutionBudgetError
from esolangs.results import ExecutionResult
from esolangs.runtime._capabilities import _AncestorEntry
from esolangs.runtime._drive import _check_snapshot_hash, _checked_halted
from esolangs.runtime._lifecycle import BoundaryCycle
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.source_hints import with_hint

if TYPE_CHECKING:
    from esolangs._cycles import (
        _BranchingStepMachine,
        _FramedMachine,
        _SteppableMachine,
    )


@dataclass(frozen=True, slots=True)
class BranchFailure:
    """One outcome that faults or would need an external input value."""

    error: EsolangError | None = None


def branch_outcomes[T](
    outcomes: list[T | BranchFailure],
) -> tuple[T | BranchFailure, ...] | None:
    """Keep failed alternatives when they share a transition with other paths."""
    if len(outcomes) == 1 and _has_backing_type(outcome := outcomes[0], BranchFailure):
        if outcome.error is not None:
            raise outcome.error from None
        return None
    return tuple(outcomes)


@dataclass(frozen=True, slots=True)
class BranchProof:
    """Explored transitions and a halted endpoint, or a closed nonhalting graph."""

    root: Hashable
    transitions: tuple[tuple[Hashable, tuple[Hashable, ...]], ...]
    halts: bool
    terminal: Hashable | None = None

    @recursive_repr()
    def __repr__(self) -> str:
        from esolangs.runtime._state import repr_snapshot_record

        return repr_snapshot_record(self, fields(BranchProof))

    def __post_init__(self) -> None:
        """Require immutable, root-reachable evidence and a valid endpoint/closure."""
        transitions = self.transitions
        if type(transitions) is not tuple or any(
            type(row) is not tuple or len(row) != 2 or type(row[1]) is not tuple
            for row in transitions
        ):
            transitions = _freeze_transitions(transitions)
            object.__setattr__(self, "transitions", transitions)
        graph = dict(transitions)
        if len(graph) != len(transitions) or type(self.halts) is not bool:
            raise ValueError("invalid branching evidence")
        reachable: set[Hashable] = set()
        pending = [self.root]
        while pending:
            state = pending.pop()
            if state not in reachable:
                reachable.add(state)
                pending.extend(graph.get(state, ()))
        if graph.keys() - reachable:
            raise ValueError("branching evidence contains unreachable states")
        if self.halts:
            if self.terminal not in reachable:
                raise ValueError("branching halt needs a reached endpoint")
            if self.terminal in graph:
                raise ValueError("branching terminal cannot have outgoing transitions")
        elif (
            self.terminal is not None
            or self.root not in graph
            or any(not outcomes for outcomes in graph.values())
            or any(
                next_state not in graph for row in graph.values() for next_state in row
            )
        ):
            raise ValueError("branching divergence needs a closed graph")

    @property
    def states_examined(self) -> int:
        """Count explored nonhalting states plus the first halted endpoint."""
        return len(self.transitions) + self.halts

    @property
    def forked(self) -> bool:
        """Whether an explored transition had multiple possible outcomes."""
        return any(len(successors) > 1 for _, successors in self.transitions)


def _freeze_transitions(
    transitions: tuple[tuple[Hashable, tuple[Hashable, ...]], ...],
) -> tuple[tuple[Hashable, tuple[Hashable, ...]], ...]:
    """Validate and freeze actual tuple storage at every graph level."""
    if not _has_backing_type(transitions, tuple):
        raise ValueError("invalid branching evidence containers")
    rows = []
    for row in tuple.__iter__(transitions):
        if not _has_backing_type(row, tuple) or tuple.__len__(row) != 2:
            raise ValueError("invalid branching evidence containers")
        state, successors = tuple.__iter__(row)
        if not _has_backing_type(successors, tuple):
            raise ValueError("invalid branching evidence containers")
        rows.append((state, tuple(tuple.__iter__(successors))))
    return tuple(rows)


class _BranchResult(NamedTuple):
    halts: bool
    forked: bool
    proof: BranchProof | None


class CycleDecision(NamedTuple):
    """A proved halt or exact repetition; branching counts states, not commands."""

    halts: bool
    commands: int | None
    cycle: BoundaryCycle | None = None
    branches: BranchProof | None = None

    def __repr__(self) -> str:
        from esolangs.runtime.memory import repr_value

        return (
            f"{type(self).__name__}(halts={self.halts!r}, "
            f"commands={repr_value(self.commands)}, cycle={self.cycle!r}, "
            f"branches={self.branches!r})"
        )


def checked_decision(value: object) -> CycleDecision:
    """Reject Boolean returns and decisions missing their claimed evidence."""
    if not _has_backing_type(value, CycleDecision) or type(value.halts) is not bool:
        raise ValueError("termination requires decision evidence")
    if value.branches is not None:
        if (
            not _has_backing_type(value.branches, BranchProof)
            or value.branches.halts is not value.halts
            or value.cycle is not None
            or value.commands is not None
        ):
            raise ValueError("invalid branching decision")
        if value.halts and value.branches.forked:
            raise ValueError("branching halt depends on this run's draws")
    elif type(value.commands) is not int or value.commands < 0:
        raise ValueError("a deterministic decision needs its command count")
    elif value.halts:
        if value.cycle is not None:
            raise ValueError("a halted decision cannot claim a cycle")
    elif (
        not _has_backing_type(value.cycle, BoundaryCycle)
        or value.cycle.commands_per_pass != 1
        or value.cycle.repeat_pass != value.commands
    ):
        raise ValueError("divergence requires command-boundary evidence")
    return value


class TerminationResult(NamedTuple):
    """Live IO observation and a proof; output finalization has not been requested."""

    observation: ExecutionResult
    decision: CycleDecision


def checked_termination(value: object) -> TerminationResult:
    """Require observed IO and valid proof without claiming finalized output."""
    if (
        not _has_backing_type(value, TerminationResult)
        or not _has_backing_type(value.observation, ExecutionResult)
        or not _has_backing_type(value.observation.output, str)
        or value.observation.completion is not None
    ):
        raise ValueError("termination requires an unfinalized IO observation")
    checked_decision(value.decision)
    steps = value.observation.steps
    if steps is not None and (
        type(steps) is not int or steps != value.decision.commands
    ):
        raise ValueError("execution steps disagree with termination evidence")
    return value


_UNCHECKED_OWNER = object()


def _proof_receiver_check(
    machine: object, *, owner: object = _UNCHECKED_OWNER
) -> Callable[[], None] | None:
    """Keep each live controller link fixed while reusing its proof state."""
    from esolangs.runtime._controller import (
        ExecutionController,
        _receiver_matches,
        _receiver_tail,
    )

    if not isinstance(machine, ExecutionController):
        return None
    wrapped = machine.vm
    tail = _receiver_tail(wrapped)
    leaf = wrapped if tail is None else tail[-1]
    if owner is not _UNCHECKED_OWNER and leaf is not owner:
        raise TypeError("debugger VM changed during proof")
    if tail is None:

        def check_one() -> None:
            if machine.vm is not wrapped:
                raise TypeError("debugger VM changed during proof")

        return check_one

    def check_chain() -> None:
        if not _receiver_matches(machine, wrapped, tail):
            raise TypeError("debugger VM changed during proof")

    return check_chain


def _exact_halt(
    steps: int, check_receiver: Callable[[], None] | None, *, evidence: bool
) -> bool | CycleDecision:
    if check_receiver is not None:
        check_receiver()
    return CycleDecision(halts=True, commands=steps) if evidence else True


def _proof_halted(
    machine: _SteppableMachine, check_receiver: Callable[[], None] | None
) -> bool:
    halted = _checked_halted(machine.halted)
    if check_receiver is not None:
        check_receiver()
    return halted


def _step_proof_receiver(
    runner: _SteppableMachine, check_receiver: Callable[[], None], completed: int
) -> None:
    """Retain invocation-local command evidence on a debugger observer fault."""
    check_receiver()
    try:
        runner.step()
    except EsolangError as error:
        from esolangs.vm import _retain_observer_steps

        _retain_observer_steps(runner, error, completed)
        raise
    check_receiver()


def _check_branch_halt(halted: object, error_type: type[TypeError]) -> None:
    """A detached terminal certificate requires a true boolean."""
    if halted is not True:
        raise error_type("branching_halted must return a bool")


_BRANCH_RUNTIME_ERRORS = (ValueError, OverflowError, RecursionError, MemoryError)


def _branch_fault(error: Exception, language: str) -> EsolangError:
    from esolangs.runtime._execution import interpreter_errors

    try:
        with interpreter_errors(
            f"the {language} interpreter recursed deeper than CPython's stack "
            "limit allows on this program",
            language=language,
        ):
            raise error
    except EsolangError as translated:
        return translated


def _owned_branch_hook_fault(
    machine: _BranchingStepMachine, adapter: object, error: Exception
) -> EsolangError | None:
    from esolangs.vm import _DelegatingVM

    if isinstance(adapter, _DelegatingVM):
        owner: object = adapter._machine  # noqa: SLF001 - enforce ownership
        if machine is owner:
            return _branch_fault(error, adapter.language)
    return None


def _branch_snapshot(machine: _BranchingStepMachine, adapter: object) -> Hashable:
    try:
        return machine.branching_snapshot()
    except EsolangError:
        raise
    except _BRANCH_RUNTIME_ERRORS as error:
        translated = _owned_branch_hook_fault(machine, adapter, error)
        if translated is None:
            raise
        raise translated from error


def _read_branch_root(
    machine: _BranchingStepMachine,
    adapter: object,
    error_type: type[TypeError],
    check_receiver: Callable[[], None] | None,
) -> tuple[Hashable, set[Hashable]]:
    """Read and hash a detached root, retaining owned IO on failure."""
    if check_receiver is not None:
        check_receiver()
    try:
        root = _branch_snapshot(machine, adapter)
        if check_receiver is not None:
            check_receiver()
        try:
            return root, {root}
        except TypeError:
            _check_snapshot_hash(root, error_type)
            raise
    except EsolangError as error:
        _retain_branch_root_fault(machine, adapter, error)
        raise


@dataclass(frozen=True, slots=True)
class _GuardedBranchCallbacks:
    """Keep detached branch callbacks tied to their original live receiver."""

    machine: _BranchingStepMachine
    check_receiver: Callable[[], None]
    capture: Callable[[object, int], tuple[Hashable, ...] | None]

    def branching_halted(self, state: Hashable) -> bool:
        self.check_receiver()
        halted = self.machine.branching_halted(state)
        self.check_receiver()
        return halted

    def branching_successors(
        self, state: Hashable, limit: int
    ) -> Sequence[Hashable] | None:
        successors = self.machine.branching_successors(state, limit)
        self.check_receiver()
        return successors

    def capture_successors(
        self, successors: object, limit: int
    ) -> tuple[Hashable, ...] | None:
        captured = self.capture(successors, limit)
        self.check_receiver()
        return captured


def _branch_callbacks(
    machine: _BranchingStepMachine,
    check_receiver: Callable[[], None] | None,
    capture: Callable[[object, int], tuple[Hashable, ...] | None],
) -> tuple[
    _BranchingStepMachine | _GuardedBranchCallbacks,
    Callable[[object, int], tuple[Hashable, ...] | None],
]:
    if check_receiver is None:
        return machine, capture
    hooks = _GuardedBranchCallbacks(machine, check_receiver, capture)
    return hooks, hooks.capture_successors


def _checked_branch_result(
    result: _BranchResult, check_receiver: Callable[[], None] | None
) -> _BranchResult:
    if check_receiver is not None:
        check_receiver()
    return result


def _branch_halt_fault(
    machine: _BranchingStepMachine,
    adapter: object,
    error: Exception,
    *,
    at_root: bool,
) -> EsolangError | TimeoutError:
    """Root and budget faults abort the search; a detached arm may fail."""
    fault: EsolangError | TimeoutError
    if _has_backing_type(error, EsolangError) or _has_backing_type(error, TimeoutError):
        fault = error
    else:
        translated = _owned_branch_hook_fault(machine, adapter, error)
        if translated is None:
            raise error
        fault = translated
    if at_root and _has_backing_type(fault, EsolangError):
        _retain_branch_root_fault(machine, adapter, fault)
    if at_root or _has_backing_type(fault, ExecutionBudgetError):
        raise fault
    return fault


def _retain_branch_root_fault(
    machine: _BranchingStepMachine, adapter: object, error: EsolangError
) -> None:
    from esolangs.vm import _capture_observation, _DelegatingVM, _record_vm_fault

    if isinstance(adapter, _DelegatingVM):
        owner: object = adapter._machine  # noqa: SLF001 - enforce ownership
        if machine is owner and error.observation is None and not error.partial_output:
            _record_vm_fault(adapter, error, _capture_observation(adapter))


def _drive_ancestor(
    state: _FramedMachine,
    runner: _SteppableMachine,
    limit: int,
    check_receiver: Callable[[], None] | None,
) -> bool:
    """Compare real pushes against live entry history, when the owner supplies it."""
    if _checked_halted(runner.halted):
        if check_receiver is not None:
            check_receiver()
        return True
    entries = cast(
        "tuple[_AncestorEntry, ...] | None", getattr(state, "_ancestor_entries", None)
    )
    ancestors: list[tuple[int, Hashable]] = []
    pushes = 0
    completed = 0
    while True:
        if pushes >= limit:
            raise with_hint(
                TimeoutError(
                    f"undecided after {limit} pushed frames: neither halted nor "
                    "repeated an ancestor's entry state"
                ),
                (
                    "increase the pushed-frame limit; changing arguments "
                    "may prevent an ancestor match"
                ),
            )
        depth_before = len(state.frames) if entries is None else len(entries)
        if check_receiver is None:
            runner.step()
        else:
            _step_proof_receiver(runner, check_receiver, completed)
            completed += 1
        if _checked_halted(runner.halted):
            if check_receiver is not None:
                check_receiver()
            return True
        if entries is not None:
            current = cast(
                "tuple[_AncestorEntry, ...]", getattr(state, "_ancestor_entries", ())
            )
            prior = entries
            entries = current
            depth = len(current)
            # A return exposes a previous token; a same-depth push replaces it.
            if not depth or (depth <= depth_before and prior[depth - 1] is current[-1]):
                continue
            pushes += 1
            if any(current[-1].key == current[i].key for i in range(depth - 1)):
                if check_receiver is not None:
                    check_receiver()
                return False
            continue
        if len(state.frames) <= depth_before:
            continue
        pushes += 1
        depth = len(state.frames) - 1
        # A frame at or above this depth belongs to a call that has since
        # returned, so drop it rather than compare against a dead ancestor.
        while ancestors and ancestors[-1][0] >= depth:
            ancestors.pop()
        key = state.frame_entry_key(state.frames[-1])
        if any(key == ancestor for _, ancestor in ancestors):
            if check_receiver is not None:
                check_receiver()
            return False
        ancestors.append((depth, key))
