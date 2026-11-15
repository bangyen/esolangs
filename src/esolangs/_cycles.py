"""The halt and cycle detectors :mod:`esolangs.vm` re-exports."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from inspect import getattr_static
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol, cast, runtime_checkable

from esolangs.exceptions import ArgumentError, EsolangError, ExecutionBudgetError
from esolangs.runtime._drive import _check_snapshot_hash, _SnapshotUnavailableError
from esolangs.runtime._lifecycle import BoundaryCycle
from esolangs.runtime._proof import BranchFailure, BranchProof, CycleDecision
from esolangs.runtime._validate import _call_signature, _has_backing_type, check_whole
from esolangs.runtime.source_hints import with_hint

if TYPE_CHECKING:
    from esolangs.runtime._vm_protocol import VM


@runtime_checkable
class _SteppableMachine(Protocol):
    """The bare step-and-ask-if-halted surface a bounded drive needs.

    No ``snapshot()``, so :class:`~esolangs.debugger.Debugger` qualifies.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""


@runtime_checkable
class _StepMachine(_SteppableMachine, Protocol):
    """The minimal step-capable surface the hang detector steps on.

    Deterministic snapshots must contain complete state, input cursor included,
    or a repeat is not a cycle. Random machines require branching analysis
    rather than a concrete-path snapshot repeat.
    """

    def snapshot(self) -> Hashable:
        """Return complete state, hashable for deterministic cycle detection.

        Opaque; ``ip``, ``memory``, ``stack`` and ``output`` are the views.
        """


@runtime_checkable
class _BranchingStepMachine(Protocol):
    """A machine whose next random choice can be enumerated exactly.

    The state is an immutable value: exploring one outcome must not
    consume a draw, input or output belonging to a sibling.
    """

    def branching_snapshot(self) -> Hashable:
        """Return the initial complete state for a branching search."""

    def branching_halted(self, state: Hashable) -> bool:
        """Whether ``state`` has halted."""

    def branching_successors(
        self, state: Hashable, limit: int
    ) -> Sequence[Hashable] | None:
        """Return every state or BranchFailure, or ``None`` when unforkable.

        ``limit`` bounds the outcomes one transition may materialize.
        """


_MISSING = object()


def _check_driver(
    machine: object,
    argument: str,
    *fields: str,
    error_type: type[EsolangError] = ArgumentError,
) -> None:
    """Accept the fields a direct driver needs, including on a forwarding VM."""
    if isinstance(machine, type) or not callable(getattr(machine, "step", None)):
        raise error_type(f"{argument} must provide a callable step()")
    _check_driver_fields(machine, argument, "halted", *fields, error_type=error_type)


def _check_driver_fields(
    machine: object,
    argument: str,
    *fields: str,
    error_type: type[EsolangError] = ArgumentError,
) -> None:
    """Check fields when the current driver phase needs them."""
    machine_type = type(machine)
    # The common case is a property on an ordinary class. A direct class
    # dictionary lookup avoids descriptor execution and an MRO search.
    declared = vars(machine_type) if type(machine_type) is type else ()
    for name in fields:
        if (
            name not in declared
            and getattr_static(machine, name, _MISSING) is _MISSING
            and not hasattr(machine, name)
        ):
            raise error_type(f"{argument} must provide a {name} attribute")


def _checked_adapter(machine: object) -> object:
    """Find the live VM beneath an observer and check for a recorded halt fault."""
    from esolangs.vm import _controller_vm, _raise_halt_fault

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
    never repeats a state and so would not return.
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


class _BranchingUnavailableError(TypeError):
    """A declared random machine cannot provide branch evidence."""


class _ProofBudgetExhaustedError(TimeoutError):
    """The detector reached its command or branching state limit."""


class _ProofSnapshotUnavailableError(TypeError):
    """The supplied VM cannot provide exact command-boundary state."""


def _proof_snapshot_reader(
    machine: _StepMachine,
) -> tuple[Callable[[], Hashable], bool]:
    """Choose a state reader and whether each returned snapshot needs checking."""
    from esolangs.debugger import Debugger
    from esolangs.vm import _DelegatingVM

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


def _proof_snapshot(reader: Callable[[], Hashable], adapter: object) -> Hashable:
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
    language, declared_random = _proof_runtime(adapter)
    halted_before = machine.halted
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
        result = _branch_search(
            branch,
            10_000 if limit is None else limit,
            evidence=evidence,
            language=language,
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
    if (require_branches or declared_random) and not halted_before:
        raise _BranchingUnavailableError(
            "termination proof for an active random machine requires branch enumeration"
        )
    if record_commands is not None:
        record_commands(0)
    if halted_before:
        return CycleDecision(halts=True, commands=0) if evidence else True
    reader, check_each_snapshot = _proof_snapshot_reader(machine)
    tortoise = _check_snapshot_hash(
        _proof_snapshot(reader, adapter), _ProofSnapshotUnavailableError
    )
    first_step = 0
    power = 1
    length = 0
    steps = 0
    while not machine.halted:
        if limit is not None and steps >= limit:
            error = _ProofBudgetExhaustedError if evidence else TimeoutError
            raise with_hint(
                error(
                    f"undecided after {limit} steps: "
                    "neither halted nor repeated a state"
                ),
                "increase limit; for growing states try a supported growth detector",
            )
        machine.step()
        steps += 1
        if record_commands is not None:
            record_commands(steps)
        length += 1
        # mypy narrows `machine.halted` to Literal[False] from the loop guard
        # and won't re-widen it across `step()`; the explicit local defeats that.
        halted: bool = machine.halted
        if halted:
            return CycleDecision(halts=True, commands=steps) if evidence else True
        state = _proof_snapshot(reader, adapter)
        if check_each_snapshot:
            _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
        if state == tortoise:
            if not check_each_snapshot and state is not tortoise:
                _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
            return (
                CycleDecision(
                    halts=False,
                    commands=steps,
                    cycle=BoundaryCycle(tortoise, first_step, steps, 1),
                )
                if evidence
                else False
            )
        if length == power:
            if not check_each_snapshot:
                _check_snapshot_hash(state, _ProofSnapshotUnavailableError)
            tortoise = state
            first_step = steps
            power *= 2
            length = 0
    return CycleDecision(halts=True, commands=steps) if evidence else True


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
    language, declared_random = _proof_runtime(_checked_adapter(machine))
    if declared_random and isinstance(machine, _SteppableMachine) and machine.halted:
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
    if isinstance(machine, _SteppableMachine) and machine.halted:
        return True
    return _branch_search(state, limit, language=language).halts


class _BranchResult(NamedTuple):
    halts: bool
    forked: bool
    proof: BranchProof | None


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
    from esolangs.vm import _DelegatingVM

    if isinstance(adapter, _DelegatingVM):
        return adapter.language, adapter._random  # noqa: SLF001
    return None, False


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


def _branch_root_states(root: Hashable) -> set[Hashable]:
    try:
        return {root}
    except TypeError:
        _check_snapshot_hash(root, _ProofSnapshotUnavailableError)
        raise


def _branch_search(
    machine: _BranchingStepMachine,
    limit: int,
    *,
    evidence: bool = False,
    language: str | None = None,
) -> _BranchResult:
    """Find a clean halt, or prove that every reachable state stays in the graph."""
    if not limit:
        raise _branch_budget(limit, evidence=evidence)
    root = machine.branching_snapshot()
    pending = deque([root])
    discovered = _branch_root_states(root)
    exceeded = False
    # Collecting for Boolean readers cost Caballo 11.5-11.6% at n=2/3.
    transitions: list[tuple[Hashable, tuple[Hashable, ...]]] | None = (
        [] if evidence else None
    )
    failure: EsolangError | TimeoutError | None = None
    forked = False
    while pending:
        state = pending.popleft()
        if machine.branching_halted(state):
            proof = (
                BranchProof(root, tuple(transitions), halts=True, terminal=state)
                if transitions is not None and not forked
                else None
            )
            return _BranchResult(halts=True, forked=forked, proof=proof)
        try:
            successors = machine.branching_successors(state, limit)
        except ExecutionBudgetError:
            raise
        except (EsolangError, TimeoutError) as error:
            if failure is None:
                failure = error
            continue
        except (ValueError, OverflowError, RecursionError, MemoryError) as error:
            if language is None:
                raise
            failure = _branch_fault(error, language) if failure is None else failure
            continue
        count = 0 if successors is None else len(successors)
        if successors is None or count > limit:
            failure = _unforkable_branch() if failure is None else failure
            continue
        if not count:
            raise TypeError("branching transition requires a successor")
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
    if failure is not None:
        raise failure
    if exceeded:
        raise _branch_budget(limit, evidence=evidence)
    proof = (
        BranchProof(root, tuple(transitions), halts=False)
        if transitions is not None
        else None
    )
    return _BranchResult(halts=False, forked=forked, proof=proof)


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
    (``f(x - 1)`` over unbounded ints); O(depth) per push.  ``limit`` bounds
    pushes examined -- a repeat shows within a few frames (three across the
    suite) -- and exhausting it raises :class:`TimeoutError`.  No call
    stack, or a random machine, raises :class:`TypeError`.
    """
    limit = check_whole(limit, "limit")
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
    if runner.halted:
        return True
    ancestors: list[tuple[int, Hashable]] = []
    pushes = 0
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
        depth_before = len(state.frames)
        runner.step()
        halted: bool = runner.halted
        if halted:
            return True
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
            return False
        ancestors.append((depth, key))


@runtime_checkable
class _TapeMachine(_SteppableMachine, Protocol):
    """A :class:`_SteppableMachine` on a rightward-growing tape of cells.

    The four members are what the growth certificate compares across two
    visits to one ``ip``, and together must be the complete state.
    ``tape`` must be the *committed* tape (brainfuck buffers a cell).
    ``ip`` is ``Hashable``: a 2D position includes its heading.
    Opting in claims the language reads and writes only the cell under
    the pointer, is translation-invariant for ``ptr >= 1``, and grows
    rightward by fresh zeros (leftward only from ``ptr == 0``, which the
    certificate's ``m >= 1`` excludes).  Absolute addresses, wrapping or
    fixed tapes, and leftward growth away from ``ptr == 0`` must not
    declare it.
    """

    @property
    def ip(self) -> Hashable:
        """The current code position, hashable and compared by equality."""

    @property
    def ptr(self) -> int:
        """The current cell pointer."""

    @property
    def tape(self) -> tuple[int, ...]:
        """The committed cells, index 0 leftmost."""

    def input_position(self) -> int:
        """Return the input cursor, so a reading loop is not a repeat."""


#: One visit's ``(pointer, tape, input cursor)`` in the growth proof.
_Snapshot = tuple[int, tuple[int, ...], int]


@dataclass
class _GrowthVisit:
    """Per-``ip`` state for the growth proof.

    Three certificates share one record: ``snapshot``/``lowest`` compare
    two consecutive visits, ``origin``/``origin_low`` the first visit to
    the current one, and the ``wave_*`` fields Brent's checkpoint for a
    phase that begins after a transient.  Each ``*_low`` is the smallest
    pointer seen over its certificate's interval; the proof is invalid
    if the period ever reached the left edge.
    """

    snapshot: _Snapshot
    lowest: int
    origin: _Snapshot
    origin_low: int
    wave_before: _Snapshot
    wave_low: int
    wave_power: int
    wave_length: int


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
    # One record per position holds all three certificates.  ``snapshot``
    # keeps the broad, one-period comparison; ``origin`` proves a steady
    # wave after its first full phase; the ``wave_*`` fields are Brent's
    # O(1)-per-position checkpoint for a phase that begins after a
    # transient.  Every minimum is updated on each step because the proof
    # is invalid if the period ever reached the left edge.
    visits: dict[Hashable, _GrowthVisit] = {}
    for completed in range(limit + 1 if limit else 0):
        if runner.halted:
            return True
        ip, ptr, tape = state.ip, state.ptr, state.tape
        for seen in visits.values():
            seen.lowest = min(seen.lowest, ptr)
            seen.origin_low = min(seen.origin_low, ptr)
            seen.wave_low = min(seen.wave_low, ptr)
        cursor = state.input_position()
        current: _Snapshot = (ptr, tape, cursor)
        visit = visits.get(ip)
        if visit is None:
            visits[ip] = _GrowthVisit(
                snapshot=current,
                lowest=ptr,
                origin=current,
                origin_low=ptr,
                wave_before=current,
                wave_low=ptr,
                wave_power=1,
                wave_length=0,
            )
        else:
            if _grows_forever(visit.snapshot, current, visit.lowest):
                return False
            if _grows_forever(visit.origin, current, visit.origin_low):
                return False
            # Unreached: by ablation each of the three arms proves every
            # growth program in the suite alone.  Kept -- the corpus is a
            # handful of programs, and an idle arm may decide a shape not
            # yet written.
            if _grows_forever(  # pragma: no cover - see above
                visit.wave_before, current, visit.wave_low
            ):
                return False
            visit.snapshot = current
            visit.lowest = ptr
            visit.wave_length += 1
            if visit.wave_length == visit.wave_power:
                visit.wave_before = current
                visit.wave_low = ptr
                visit.wave_power *= 2
                visit.wave_length = 0
        if completed == limit:
            break
        runner.step()
    if runner.halted:
        return True
    raise with_hint(
        TimeoutError(
            f"undecided after {limit} steps: neither halted nor grew by a "
            "provable translation"
        ),
        "increase limit; for repeated exact states try run_until_halt_or_cycle",
    )


def _grows_forever(
    before: _Snapshot,
    after: _Snapshot,
    lowest: int,
) -> bool:
    """Whether ``after`` is ``before`` translated right by the growth."""
    ptr_before, tape_before, input_before = before
    ptr_after, tape_after, input_after = after
    displacement = ptr_after - ptr_before
    return (
        input_after == input_before
        and displacement > 0
        and len(tape_after) == len(tape_before) + displacement
        and lowest >= 1
        and all(
            tape_after[i + displacement] == tape_before[i]
            for i in range(lowest, len(tape_before))
        )
    )


@runtime_checkable
class _AffineMachine(_SteppableMachine, Protocol):
    """A machine whose cells grow in *value* on a tape that does not grow.

    A loop may stay one to five cells wide while a cell climbs by a
    constant each lap, on unbounded Python ints.  ``values`` may grow
    (compared by subtraction); ``key`` is everything else (equality);
    ``clamp_slack`` is the one place a value changes behaviour.  Opting
    in claims control flow is independent of ``values`` (no branch),
    every operation is affine
    (``acc += tape[ptr]``, ``tape[ptr] + 1 - acc``, resets to 0), and
    every departure is a ``max(0, ...)`` reported by ``clamp_slack``
    *before* the clamping step.  The clamp claim is load-bearing: a slack
    shrinking a little each lap flips after a hundred laps.
    """

    @property
    def key(self) -> Hashable:
        """The state compared by equality: code position, pointer, width."""

    @property
    def values(self) -> tuple[int, ...]:
        """The unbounded values, compared by subtraction, in a fixed order."""

    @property
    def clamp_slack(self) -> int | None:
        """The pending step's clamped quantity, or ``None`` if it clamps none."""

    def input_position(self) -> int:
        """Return the input cursor, so a reading loop is not a repeat."""


#: One visit's ``(step index, values, input cursor)`` in the affine proof.
_Visit = tuple[int, tuple[int, ...], int]


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
    # One slack per step in a single log, and per key the last three steps
    # that visited it, so a lap is a slice rather than a list of its own.
    # Collecting slacks per waiting key would append once for every key
    # still unrevisited -- quadratic on a program whose key never repeats,
    # such as ``>`` alone widening the tape every step.
    slacks: list[int | None] = []
    visits: dict[Hashable, list[_Visit]] = {}
    for index in range(limit + 1 if limit else 0):
        if runner.halted:
            return True
        slacks.append(state.clamp_slack)
        key = state.key
        seen = visits.setdefault(key, [])
        seen.append((index, state.values, state.input_position()))
        del seen[:-3]
        if len(seen) == 3 and _climbs_forever(seen, slacks):
            return False
        if index == limit:
            break
        runner.step()
    if runner.halted:
        return True
    raise with_hint(
        TimeoutError(
            f"undecided after {limit} steps: neither halted nor climbed by a "
            "provable affine step"
        ),
        "increase limit; for repeated exact states try run_until_halt_or_cycle",
    )


def _climbs_forever(
    visits: list[_Visit],
    slacks: list[int | None],
) -> bool:
    """Whether three visits advance affinely with every clamp holding.

    The two laps are the stretches of ``slacks`` between the visits' steps.
    """
    (start, first, cursor), (split, second, middle), (end, third, last) = visits
    if cursor != middle or middle != last:
        return False
    if not len(first) == len(second) == len(third):
        return False
    step = tuple(b - a for a, b in zip(first, second, strict=True))
    if step != tuple(c - b for b, c in zip(second, third, strict=True)):
        return False
    if not any(step) or any(delta < 0 for delta in step):
        return False
    return _clamps_hold(slacks[start:split], slacks[split:end])


def _clamps_hold(before: list[int | None], after: list[int | None]) -> bool:
    """Whether two laps clamped alike, with no slack drifting toward a flip.

    A clamp at the floor may only sink; one above it may only rise.
    """
    if len(before) != len(after):
        return False
    for previous, current in zip(before, after, strict=True):
        if (previous is None) != (current is None):
            return False
        if previous is None or current is None:
            continue
        if (previous >= 0) != (current >= 0):
            return False
        if previous >= 0 and current < previous:
            return False
        if previous < 0 and current > previous:
            return False
    return True


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
) -> int | None:
    """Count completed commands on halt or fault, returning None on a stop."""
    _checked_adapter(machine)
    steps = 0
    try:
        while not machine.halted:
            if limit is not None and steps >= limit:
                return None
            if stop is not None and stop():
                return None
            machine.step()
            steps += 1
    except EsolangError as error:
        if on_fault is not None:
            on_fault(error, steps)
        raise
    return steps
