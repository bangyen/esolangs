"""Observe live machine callbacks while collecting termination evidence."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from esolangs.exceptions import EsolangError, ExecutionBudgetError
from esolangs.runtime._capabilities import _AncestorEntry
from esolangs.runtime._drive import _check_snapshot_hash, _checked_halted
from esolangs.runtime._proof import CycleDecision, _BranchResult
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.source_hints import with_hint

if TYPE_CHECKING:
    from esolangs._cycles import _FramedMachine
    from esolangs.runtime._vm_protocol import _BranchingStepMachine, _SteppableMachine


class _ProofBudgetExhaustedError(TimeoutError):
    """The detector reached its command or branching state limit."""


class _ProofSnapshotUnavailableError(TypeError):
    """The supplied VM cannot provide exact command-boundary state."""


def _proof_traits(adapter: object) -> tuple[str | None, bool]:
    """Return the adapter's language and whether it can draw."""
    from esolangs.runtime._vm_adapter import _DelegatingVM

    if isinstance(adapter, _DelegatingVM):
        return adapter.language, adapter._random  # noqa: SLF001
    return None, False


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
        from esolangs.runtime._vm_adapter import _retain_observer_steps

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
    from esolangs.runtime._vm_adapter import _DelegatingVM

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
    from esolangs.runtime._vm_adapter import (
        _capture_observation,
        _DelegatingVM,
        _record_vm_fault,
    )

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
