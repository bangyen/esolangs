"""Explore reachable random-machine states within a proof budget."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Hashable, Sequence
from itertools import islice

from esolangs.exceptions import EsolangError, ExecutionBudgetError
from esolangs.runtime._drive import _check_snapshot_hash
from esolangs.runtime._proof import BranchFailure, BranchProof, _BranchResult
from esolangs.runtime._proof_runtime import (
    _BRANCH_RUNTIME_ERRORS,
    _branch_callbacks,
    _branch_fault,
    _branch_halt_fault,
    _check_branch_halt,
    _checked_branch_result,
    _read_branch_root,
)
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime._vm_protocol import _BranchingStepMachine
from esolangs.runtime.source_hints import with_hint


class _BranchingUnavailableError(TypeError):
    """A declared random machine cannot provide branch evidence."""


class _ProofBudgetExhaustedError(TimeoutError):
    """The detector reached its command or branching state limit."""


class _ProofSnapshotUnavailableError(TypeError):
    """The supplied VM cannot provide exact command-boundary state."""


def _unforkable_branch() -> TimeoutError:
    return with_hint(
        TimeoutError(
            "undecided: a branching transition cannot be safely forked: "
            "it needs input or exceeds the outcome budget"
        ),
        (
            "increase the branch limit, or use fixed input and a seeded "
            "single-path run; that does not decide all random paths"
        ),
    )


def _branch_budget(limit: int, *, evidence: bool) -> TimeoutError:
    error_type = _ProofBudgetExhaustedError if evidence else TimeoutError
    return with_hint(
        error_type(
            f"undecided after {limit} branching states: the reachable "
            "graph may be unbounded"
        ),
        "increase the branching state limit if feasible; the result remains undecided",
    )


def _proof_runtime(adapter: object) -> tuple[str | None, bool]:
    from esolangs.runtime._vm_adapter import _DelegatingVM

    if isinstance(adapter, _DelegatingVM):
        return adapter.language, adapter._random  # noqa: SLF001
    return None, False


def _bounded_branch_sequence(result: object, limit: int) -> tuple[Hashable, ...] | None:
    """Capture foreign successor containers within the declared state budget."""
    if not isinstance(result, Sequence):
        raise _BranchingUnavailableError(
            "branching_successors must return a sequence or None"
        )
    try:
        count = len(result)
        if count > limit:
            return None
        items = iter(result)
        successors = tuple(islice(items, count))
        end = object()
        if len(successors) == count and next(items, end) is end:
            return successors
    except (TypeError, ValueError, OverflowError) as error:
        raise _BranchingUnavailableError(
            "branching_successors must return a finite sequence"
        ) from error
    raise _BranchingUnavailableError(
        "branching successor count disagrees with its sequence"
    )


def _branch_search(
    machine: _BranchingStepMachine,
    limit: int,
    *,
    check_receiver: Callable[[], None] | None = None,
    evidence: bool = False,
    adapter: object,
) -> _BranchResult:
    """Find a clean halt, or prove that every reachable state stays in the graph."""
    if not limit:
        raise _branch_budget(limit, evidence=evidence)
    root, discovered = _read_branch_root(
        machine, adapter, _ProofSnapshotUnavailableError, check_receiver
    )
    hooks, capture = _branch_callbacks(
        machine, check_receiver, _bounded_branch_sequence
    )
    language, _ = _proof_runtime(adapter)
    pending = deque([root])
    exceeded = False
    # Collecting for Boolean readers cost Caballo 11.5-11.6% at n=2/3.
    transitions: list[tuple[Hashable, tuple[Hashable, ...]]] | None = (
        [] if evidence else None
    )
    failure: EsolangError | TimeoutError | None = None
    forked = False
    while pending:
        state = pending.popleft()
        try:
            halted = hooks.branching_halted(state)
        except (EsolangError, TimeoutError, *_BRANCH_RUNTIME_ERRORS) as error:
            fault = _branch_halt_fault(machine, adapter, error, at_root=state is root)
            failure = fault if failure is None else failure
            continue
        if halted is not False:
            _check_branch_halt(halted, _BranchingUnavailableError)
            proof = (
                BranchProof(root, tuple(transitions), halts=True, terminal=state)
                if transitions is not None and not forked
                else None
            )
            return _checked_branch_result(
                _BranchResult(halts=True, forked=forked, proof=proof), check_receiver
            )
        try:
            successors = hooks.branching_successors(state, limit)
        except ExecutionBudgetError:
            raise
        except (EsolangError, TimeoutError) as error:
            failure = error if failure is None else failure
            continue
        except _BRANCH_RUNTIME_ERRORS as error:
            if language is None:
                raise
            failure = _branch_fault(error, language) if failure is None else failure
            continue
        successors = (
            successors
            if type(successors) is tuple or successors is None
            else capture(successors, limit)
        )
        count = 0 if successors is None else len(successors)
        if successors is None or count > limit:
            failure = _unforkable_branch() if failure is None else failure
            continue
        if not count:
            raise _BranchingUnavailableError(
                "branching transition requires a successor"
            )
        forked = forked or count > 1
        if transitions is not None:
            transitions.append((state, tuple(successors)))
        for outcome in successors:
            if _has_backing_type(outcome, BranchFailure):
                if failure is None:
                    failure = (
                        _unforkable_branch() if outcome.error is None else outcome.error
                    )
                # Only a closed graph or an unforked clean run supplies evidence.
                transitions = None
                continue
            try:
                if outcome in discovered:
                    continue
                if len(discovered) == limit:
                    exceeded = True
                else:
                    discovered.add(outcome)
                    pending.append(outcome)
            except TypeError:
                _check_snapshot_hash(outcome, _ProofSnapshotUnavailableError)
                raise
    if failure is not None or exceeded:
        raise (
            failure if failure is not None else _branch_budget(limit, evidence=evidence)
        )
    proof = (
        BranchProof(root, tuple(transitions), halts=False)
        if transitions is not None
        else None
    )
    return _checked_branch_result(
        _BranchResult(halts=False, forked=forked, proof=proof), check_receiver
    )
