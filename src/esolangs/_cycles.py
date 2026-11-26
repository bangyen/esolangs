"""The halt and cycle detectors :mod:`esolangs.vm` re-exports."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from inspect import getattr_static
from typing import Any, Protocol, cast, runtime_checkable

from esolangs.exceptions import ArgumentError, EsolangError
from esolangs.runtime._branch_search import (
    _branch_search,
    _BranchingUnavailableError,
    _proof_runtime,
    _ProofBudgetExhaustedError,
    _ProofSnapshotUnavailableError,
)
from esolangs.runtime._drive import (
    _check_snapshot_hash,
    _checked_halted,
    _SnapshotUnavailableError,
)
from esolangs.runtime._growth import (
    _AffineMachine,
    _drive_tape_growth,
    _drive_value_growth,
    _TapeMachine,
)
from esolangs.runtime._lifecycle import BoundaryCycle
from esolangs.runtime._proof import CycleDecision
from esolangs.runtime._proof_runtime import (
    _drive_ancestor,
    _exact_halt,
    _proof_halted,
    _proof_receiver_check,
)
from esolangs.runtime._validate import _call_signature, check_whole
from esolangs.runtime._vm_protocol import (
    VM,
    _BranchingStepMachine,
    _check_driver,
    _StepMachine,
    _SteppableMachine,
)
from esolangs.runtime.source_hints import with_hint


def _checked_adapter(machine: object) -> object:
    """Find the live VM beneath an observer and check for a recorded halt fault."""
    from esolangs.runtime._vm_adapter import _controller_vm, _raise_halt_fault

    _raise_halt_fault(machine)
    return _controller_vm(machine)


def _protocol_state(machine: object, adapter: object, protocol: type[Any]) -> object:
    """Prefer the first supplied proof protocol before wrapped interpreter state."""
    from esolangs.runtime._controller import ExecutionController

    if isinstance(machine, protocol):
        state = machine
    elif isinstance(machine, ExecutionController):
        return _protocol_state(machine.vm, adapter, protocol)
    elif adapter is not machine and isinstance(adapter, protocol):
        state = adapter
    else:
        state = getattr(adapter, "_machine", None)
        if not isinstance(state, protocol):
            return None
    _check_proof_methods(
        state,
        _PROOF_METHODS[protocol],
        error_type=_BranchingUnavailableError
        if protocol is _BranchingStepMachine
        else TypeError,
    )
    return state


def _check_proof_methods(
    machine: object,
    methods: tuple[str, ...],
    *,
    error_type: type[TypeError] = TypeError,
) -> None:
    """Runtime protocol membership alone accepts non-callable methods."""
    if isinstance(machine, type):
        raise error_type("a proof requires a machine instance")
    for name in methods:
        if not callable(getattr(machine, name, None)):
            raise error_type(f"{type(machine).__name__}.{name} must be callable")


def _unwrap(machine: object, protocol: type[Any], role: str, *, hint: str) -> object:
    """Find proof state on a machine, its VM, or the underlying interpreter.

    The protocol is tried before the unwrap, so a raw machine is handed
    back as is.  ``role`` names what the argument failed to be.
    ``protocol`` is ``type[Any]`` with a ``cast`` at each caller: mypy
    refuses a protocol class where ``type[T]`` is expected.
    """
    state = _protocol_state(machine, _checked_adapter(machine), protocol)
    if state is not None:
        return state
    raise with_hint(
        TypeError(
            f"{getattr(machine, 'language', type(machine).__name__)} is not {role}: "
            "neither it nor any machine "
            "it wraps provides the required members"
        ),
        hint,
    )


def _proof_runner(machine: object, state: _SteppableMachine) -> _SteppableMachine:
    """Keep step effects and fault translation on the supplied live surface."""
    if machine is not state and isinstance(machine, _SteppableMachine):
        _check_proof_methods(machine, ("step",))
        return machine
    return state


def _refuse_random(machine: object, proof: str) -> None:
    """Raise when ``machine`` draws: ``proof`` assumes the next lap repeats.

    Branching cannot stand in -- a growing state never repeats -- so a
    random machine is refused rather than handed over.
    """
    adapter = _checked_adapter(machine)
    _, declared_random = _proof_runtime(adapter)
    branch = _protocol_state(machine, adapter, _BranchingStepMachine)
    live = machine if isinstance(machine, _SteppableMachine) else branch
    if (declared_random or branch is not None) and not getattr(live, "halted", True):
        raise with_hint(
            TypeError(
                f"random machines: a {proof} proof assumes each lap repeats "
                "the last, and a draw can change the next one"
            ),
            "bound the run instead; run_until_halt_or_all_branches_cycle "
            "decides exact cycles over every draw",
        )


def run_until_halt_or_cycle(
    machine: _StepMachine | VM, limit: int | None = None
) -> bool:
    """Step ``machine`` until it halts or revisits an exact state.

    A random language's machine is decided by branching instead (``limit``
    then counts branching states, its default when ``None``): ``False`` when
    every draw cycles, ``True`` when the program never drew and halts, and
    :class:`TypeError` when this run's own draws decide it or branch
    enumeration is unavailable.  A repeated deterministic snapshot *proves* a
    hang.  ``True`` on a halt, ``False`` once a cycle is proven.  Unbounded
    growth never repeats and is :func:`run_until_halt_or_growth`'s.  Brent's
    algorithm uses O(1) snapshots and may run up to ~2x past the cycle's start.

    ``limit`` bounds the steps as the sibling detectors do, raising
    :class:`TimeoutError` rather than answer.  ``None`` (default) is the
    unbounded search; bound it when the machine may *grow* instead, which
    never repeats a state and so would not return. A live debugger proof
    requires the wrapped VM to stay fixed.
    """
    return cast("bool", _drive_halt_or_cycle(machine, limit, evidence=False))


def _halt_or_cycle_result(
    machine: _StepMachine | VM,
    limit: int | None = None,
    *,
    require_branches: bool = False,
    record_commands: Callable[[int], None] | None = None,
) -> CycleDecision:
    """Retain the command boundaries or complete branching evidence of a decision."""
    return cast(
        "CycleDecision",
        _drive_halt_or_cycle(
            machine,
            limit,
            evidence=True,
            require_branches=require_branches,
            record_commands=record_commands,
        ),
    )


class _DrawDependentHaltError(TypeError):
    """Branch exploration found a halt that depends on a draw."""


def _proof_snapshot_reader(
    machine: _StepMachine,
) -> tuple[Callable[[], Hashable], bool]:
    """Choose a state reader and whether each returned snapshot needs checking."""
    from esolangs.debugger import Debugger
    from esolangs.runtime._vm_adapter import _DelegatingVM

    reader = getattr_static(machine, "snapshot", None)
    if isinstance(machine, _DelegatingVM) and reader is _DelegatingVM.snapshot:
        return (
            machine._snapshot_value,  # noqa: SLF001 - proof owns state validation
            not machine._uses_installed_snapshots(),  # noqa: SLF001
        )
    if isinstance(machine, Debugger) and reader is Debugger.snapshot:
        wrapped = machine.vm
        if isinstance(wrapped, Debugger) and (
            getattr_static(wrapped, "snapshot", None) is Debugger.snapshot
        ):
            return _proof_snapshot_reader(wrapped)
        if isinstance(wrapped, _DelegatingVM) and (
            getattr_static(wrapped, "snapshot", None) is _DelegatingVM.snapshot
        ):
            return (
                wrapped._snapshot_value,  # noqa: SLF001 - proof owns state validation
                not wrapped._uses_installed_snapshots(),  # noqa: SLF001
            )
        return machine._snapshot_value, True  # noqa: SLF001 - proof checks the state

    def read_live() -> Hashable:
        return machine.snapshot()

    return read_live, True


def _proof_snapshot(
    reader: Callable[[], Hashable],
    adapter: object,
    steps: int | None,
    *,
    check_hash: bool = False,
) -> Hashable:
    try:
        state = reader()
    except _SnapshotUnavailableError as error:
        if error.vm is not adapter:
            raise
        raise with_hint(
            _ProofSnapshotUnavailableError(
                "exact-cycle proof requires a callable snapshot()"
            ),
            "provide a machine with a snapshot of its complete state",
        ) from error
    except EsolangError as error:
        from esolangs.runtime._vm_adapter import _DelegatingVM, _retain_fault_steps

        if steps is not None and isinstance(adapter, _DelegatingVM):
            _retain_fault_steps(adapter, error, steps)
        raise
    if check_hash:
        try:
            _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
        except EsolangError as error:
            from esolangs.runtime._vm_adapter import _retain_snapshot_key_fault

            _retain_snapshot_key_fault(reader, error, steps)
            raise
    return state


def _drive_halt_or_cycle(
    machine: _StepMachine | VM,
    limit: int | None,
    *,
    evidence: bool,
    require_branches: bool = False,
    record_commands: Callable[[int], None] | None = None,
) -> bool | CycleDecision:
    """Share transitions; Boolean readers need no retained branching graph."""
    if limit is not None:
        limit = check_whole(limit, "limit")
    supplied = machine
    machine = cast(
        _StepMachine,
        _unwrap(
            machine,
            _StepMachine,
            "steppable with a snapshot",
            hint="pass make_vm(...) or a machine with step, halted and snapshot",
        ),
    )
    adapter = _checked_adapter(machine)
    _, declared_random = _proof_runtime(adapter)
    check_receiver = _proof_receiver_check(supplied, owner=adapter)
    halted_before = _proof_halted(machine, check_receiver)
    branch = (
        None
        if halted_before
        else cast(
            "_BranchingStepMachine | None",
            _protocol_state(machine, adapter, _BranchingStepMachine),
        )
    )
    # A seeded random program can repeat its visible state, then halt: the
    # next draw is not in the snapshot, so a repeat proves nothing.  Branching
    # keeps the verdicts that hold whatever this run draws.  It ignores the
    # machine's own draw source, so "some path halts" after a fork is not
    # this run's answer (a FirstDraw(0) coin loops where the other halts).
    if branch is not None:
        return _branch_cycle(
            branch, limit, check_receiver, evidence=evidence, adapter=adapter
        )
    if (require_branches or declared_random) and not halted_before:
        raise _BranchingUnavailableError(
            "termination proof for an active random machine requires branch enumeration"
        )
    if record_commands is not None:
        record_commands(0)
    if halted_before:
        return _exact_halt(0, check_receiver, evidence=evidence)
    reader, check_each_snapshot = _proof_snapshot_reader(machine)
    tortoise = _proof_snapshot(
        reader, adapter, None if evidence else 0, check_hash=True
    )
    first_step = length = steps = 0
    power = 1
    while not _checked_halted(machine.halted):
        if check_receiver is not None:
            check_receiver()
        if limit is not None and steps >= limit:
            error = _ProofBudgetExhaustedError if evidence else TimeoutError
            raise with_hint(
                error(
                    f"undecided after {limit} steps: "
                    "neither halted nor repeated a state"
                ),
                "increase limit; for growing states try a supported growth detector",
            )
        try:
            machine.step()
        except EsolangError as error:
            if not evidence:
                from esolangs.runtime._vm_adapter import _retain_observer_steps

                _retain_observer_steps(machine, error, steps)
            raise
        steps += 1
        if record_commands is not None:
            record_commands(steps)
        length += 1
        if check_receiver is not None:
            check_receiver()
        if _checked_halted(machine.halted):
            return _exact_halt(steps, check_receiver, evidence=evidence)
        state = _proof_snapshot(reader, adapter, None if evidence else steps)
        at_checkpoint = length == power
        try:
            if check_each_snapshot:
                _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
            repeated = bool(state == tortoise)
            if not check_each_snapshot and (
                state is not tortoise if repeated else at_checkpoint
            ):
                _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
        except EsolangError as error:
            from esolangs.runtime._vm_adapter import _retain_snapshot_key_fault

            _retain_snapshot_key_fault(reader, error, None if evidence else steps)
            raise
        if repeated:
            return _exact_repeat(
                tortoise, first_step, steps, reader, check_receiver, evidence=evidence
            )
        if at_checkpoint:
            tortoise = state
            first_step = steps
            power *= 2
            length = 0
    return _exact_halt(steps, check_receiver, evidence=evidence)


def _exact_repeat(
    state: Hashable,
    first_step: int,
    steps: int,
    reader: Callable[[], Hashable],
    check_receiver: Callable[[], None] | None,
    *,
    evidence: bool,
) -> bool | CycleDecision:
    if check_receiver is not None:
        check_receiver()
    if not evidence:
        return False
    try:
        cycle = BoundaryCycle(state, first_step, steps, 1)
    except EsolangError as error:
        from esolangs.runtime._vm_adapter import _retain_snapshot_key_fault

        _retain_snapshot_key_fault(reader, error, None)
        raise
    return CycleDecision(halts=False, commands=steps, cycle=cycle)


def _branch_cycle(
    branch: _BranchingStepMachine,
    limit: int | None,
    check_receiver: Callable[[], None] | None,
    *,
    evidence: bool,
    adapter: object,
) -> bool | CycleDecision:
    result = _branch_search(
        branch,
        10_000 if limit is None else limit,
        check_receiver=check_receiver,
        evidence=evidence,
        adapter=adapter,
    )
    if not result.halts or not result.forked:
        return (
            CycleDecision(result.halts, None, branches=result.proof)
            if evidence
            else result.halts
        )
    raise with_hint(
        _DrawDependentHaltError(
            "random machines: some draws halt this program. This proof leaves "
            "open whether this run's result depends on its own draws"
        ),
        "use run_until_halt_or_all_branches_cycle for the any-draw question",
    )


def run_until_halt_or_all_branches_cycle(
    machine: _BranchingStepMachine | VM, limit: int = 10_000
) -> bool:
    """Explore random outcomes until one halts or every path is cyclic.

    ``True`` when *some* sequence of draws halts, ``False`` only once the
    reachable graph is finite with no halted state.  ``limit`` bounds
    distinct states and outcomes per step. A fault or unforkable transition
    leaves the result undecided unless another path halts. On an undecided
    result, the first fault or :class:`TimeoutError` is raised.
    A language with no random instruction raises :class:`TypeError`.
    """
    limit = check_whole(limit, "limit")
    adapter = _checked_adapter(machine)
    check_receiver = _proof_receiver_check(machine, owner=adapter)
    _, random = _proof_runtime(adapter)
    if (
        random
        and isinstance(machine, _SteppableMachine)
        and _proof_halted(machine, check_receiver)
    ):
        return True
    state = cast(
        _BranchingStepMachine,
        _unwrap(
            machine,
            _BranchingStepMachine,
            "branch-enumerable",
            hint="use a machine with branching_snapshot, "
            "branching_halted and branching_successors",
        ),
    )
    if isinstance(machine, _SteppableMachine) and _proof_halted(
        machine, check_receiver
    ):
        return True
    return _branch_search(
        state, limit, check_receiver=check_receiver, adapter=adapter
    ).halts


@runtime_checkable
class _FramedMachine(_SteppableMachine, Protocol):
    """A :class:`_SteppableMachine` that also exposes its call stack.

    ``frames`` is outermost first; ``frame_entry_key`` is what a frame is
    about to run (function, bindings, input cursor).
    """

    @property
    def frames(self) -> Sequence[object]:
        """The live call stack, outermost frame first."""

    def frame_entry_key(self, frame: object) -> Hashable:
        """Return ``frame``'s entry state, hashable and comparable."""


def run_until_halt_or_ancestor(machine: _FramedMachine | VM, limit: int = 64) -> bool:
    """Step ``machine`` until it halts or a call provably replays an ancestor.

    Infinite recursion pushes a frame per step, so snapshots never repeat;
    each pushed frame is compared with those beneath it, and an equal
    ``frame_entry_key`` means it replays what the ancestor is still inside.
    ``True`` on a halt, ``False`` once such a frame lands.  The input
    position carries the soundness (a base case one read away would
    otherwise be called a hang).  Misses bindings that differ every lap
    (``f(x - 1)`` over unbounded ints); O(depth) per push. Installed framed
    VMs retain entry state across calls to this detector. The limit bounds
    new pushes examined. Exhausting it raises :class:`TimeoutError`.
    No call stack, or a random machine, raises :class:`TypeError`.
    """
    limit = check_whole(limit, "limit")
    check_receiver = _proof_receiver_check(machine)
    _refuse_random(machine, "replayed-ancestor")
    state = cast(
        _FramedMachine,
        _unwrap(
            machine,
            _FramedMachine,
            "framed",
            hint="use a machine with frames and frame_entry_key; "
            "otherwise try exact-state cycle detection",
        ),
    )
    runner = _proof_runner(machine, state)
    return _drive_ancestor(state, runner, limit, check_receiver)


def run_until_halt_or_growth(machine: _TapeMachine | VM, limit: int = 100_000) -> bool:
    """Step ``machine`` until it halts or provably grows without bound.

    ``+[>+]`` grows a cell a lap, so the snapshot is always new.  This
    compares two consecutive visits to one ``ip``; with ``d`` the pointer
    displacement and ``m`` the lowest cell reached between them, a hang
    is written when all of:

    - the input cursor did not move,
    - ``d > 0`` and the tape grew by exactly ``d`` fresh cells,
    - ``m >= 1``, so the period never touched the left edge,
    - ``tape2[i + d] == tape1[i]`` for every ``m <= i < len(tape1)``.

    Then the second visit is the first translated by ``d`` on the cells
    it can still reach, and by translation invariance the period replays
    forever.  ``m >= 1`` licenses the translation; ``i >= m`` rather than
    ``i >= 0`` is what proves ``+[>++]`` (cell 0 keeps a 1).  A Brent
    checkpoint per position finds a repeating phase of any length.
    ``d == 0`` (``+[<+]``) is :func:`run_until_halt_or_cycle`'s;
    ``>+[[<]>[>]+]`` is out of reach (visits share a frozen prefix, and a
    machine counting its walk into ``ip`` could halt on a count the pair
    never saw).  ``limit`` is in steps and raises :class:`TimeoutError`;
    no tape, or a random machine, raises :class:`TypeError`.
    """
    limit = check_whole(limit, "limit")
    check_receiver = _proof_receiver_check(machine)
    _refuse_random(machine, "tape-growth")
    state = cast(
        _TapeMachine,
        _unwrap(
            machine,
            _TapeMachine,
            "a tape machine",
            hint="use a compatible rightward-growing tape machine; "
            "otherwise try exact-state cycle detection",
        ),
    )
    runner = _proof_runner(machine, state)
    return _drive_tape_growth(state, runner, limit, check_receiver)


def run_until_halt_or_value_growth(
    machine: _AffineMachine | VM, limit: int = 20_000
) -> bool:
    """Step ``machine`` until it halts or provably grows in value forever.

    For fixed-width tapes whose *cells* grow.  With ``v1``, ``v2``, ``v3``
    the ``values`` at three consecutive visits to one ``key``, a hang is
    reported when all of:

    - the input cursor did not move,
    - ``key`` is equal at all three,
    - ``v2 - v1 == v3 - v2``, non-zero, no negative component,
    - the two laps agree at every clamp: same side, slack not drifting.

    Then the lap is an affine map ``v -> v + d`` and, control flow not
    reading values, repeats forever.  Seen *twice* because one observation
    is consistent with anything next.  ``limit`` is in steps; a step costs
    the whole tape, and 20_000 is the measured turn of that curve (~1.6s
    worst case, under a millisecond on the two programs this is for).
    Bounded values raise :class:`TypeError`: a climbing byte wraps.  So does a
    random machine.
    """
    limit = check_whole(limit, "limit")
    check_receiver = _proof_receiver_check(machine)
    _refuse_random(machine, "value-growth")
    state = cast(
        _AffineMachine,
        _unwrap(
            machine,
            _AffineMachine,
            "an affine machine",
            hint="use a machine with unbounded affine values; wrapping "
            "cells need exact-state cycle detection",
        ),
    )
    runner = _proof_runner(machine, state)
    return _drive_value_growth(state, runner, limit, check_receiver)


_PROOF_METHODS: dict[type[Any], tuple[str, ...]] = {
    _StepMachine: ("step", "snapshot"),
    _BranchingStepMachine: (
        "branching_snapshot",
        "branching_halted",
        "branching_successors",
    ),
    _FramedMachine: ("step", "frame_entry_key"),
    _TapeMachine: ("step", "input_position"),
    _AffineMachine: ("step", "input_position"),
}


def run_until_halt(
    machine: _SteppableMachine | VM,
    limit: int | None = None,
    *,
    stop: Callable[[], bool] | None = None,
) -> bool:
    """Step ``machine`` until it halts, or the budget or ``stop`` ends it.

    Proves nothing: ``True`` halted, ``False`` still going.  ``limit`` in
    steps, ``None`` unbounded. The zero-argument ``stop`` callback is
    checked *before* a permitted step. The machine is left where it stopped.
    """
    if limit is not None:
        limit = check_whole(limit, "limit")
    if stop is not None:
        _check_stop(stop)
    _check_driver(machine, "machine")
    return _drive_until_halt(machine, limit, stop=stop) is not None


def _check_stop(stop: object) -> None:
    """Refuse malformed predicates before a zero budget or halt hides them."""
    if not callable(stop):
        raise ArgumentError("stop must be callable or None")
    try:
        parameters = _call_signature(stop)
    except (TypeError, ValueError):
        return  # Callables such as bool do not expose an inspectable signature.
    try:
        parameters.bind()
    except TypeError as error:
        raise ArgumentError("stop must be callable without arguments") from error


def _drive_until_halt(
    machine: _SteppableMachine | VM,
    limit: int | None,
    *,
    stop: Callable[[], bool] | None = None,
    on_fault: Callable[[EsolangError, int], None] | None = None,
    check_active: Callable[[], None] | None = None,
) -> int | None:
    """Count completed commands on halt or fault, returning None on a stop."""
    _checked_adapter(machine)
    steps = 0
    try:
        while not _checked_halted(machine.halted):
            if check_active is not None:
                check_active()
            if limit is not None and steps >= limit:
                return None
            if stop is not None:
                requested = bool(stop())
                if _checked_halted(machine.halted):
                    break
                if requested:
                    return None
            machine.step()
            steps += 1
    except EsolangError as error:
        if on_fault is not None:
            on_fault(error, steps)
        raise
    _checked_adapter(machine)
    return steps
