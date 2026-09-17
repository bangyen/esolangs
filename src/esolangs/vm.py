"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps a registered interpreter in a :class:`VM` exposing the
run state between commands; ``ip``/``memory``/``stack`` are language-shaped.

Three conventions defeat ``while not vm.halted: vm.step()``, so the VM
reports them: ``self_halts`` (``halted`` never becomes true),
``dumps_on_the_post_halt_step`` (output lands one step after the halt),
and ``steppable_to_answer`` (A Painter Ant alone; use :func:`esolangs.run`).

The five hang detectors -- :func:`run_until_halt_or_cycle`,
:func:`run_until_halt_or_all_branches_cycle`,
:func:`run_until_halt_or_ancestor`, :func:`run_until_halt_or_growth`,
:func:`run_until_halt_or_value_growth` -- take a :class:`VM` or the state
it wraps, and raise :class:`TypeError` for a language lacking their
sub-protocol.  :func:`run_until_halt` proves nothing.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Hashable, Sequence
from functools import cache
from typing import Any, Protocol, cast, runtime_checkable

from esolangs.exceptions import (
    InterpreterLimitError,
    ProgramError,
    UnknownLanguageError,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import RUNNERS, resolve


@runtime_checkable
class _StepMachine(Protocol):
    """The minimal step-capable surface the hang detector steps on.

    ``snapshot()`` must be the *complete* state, input cursor included, or a
    "repeat" is not a real cycle.
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    def snapshot(self) -> Hashable:
        """Return the complete internal state, hashable for cycle detection.

        Opaque; ``ip``, ``memory``, ``stack`` and ``output`` are the views.
        """


@runtime_checkable
class _StepMachineWithShape(_StepMachine, Protocol):
    """A step-capable machine that also describes its own VM shape.

    Wrapped by :class:`_DelegatingVM` with no per-language code here.
    ``Sequence``, not ``list``: ``list`` is invariant, so ``list[int]``
    could never satisfy ``list[object]``; the VM materializes the copy.
    """

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The current code/instruction position."""

    @property
    def memory(self) -> Sequence[int]:
        """The addressable cells, or empty where there is no such store."""

    @property
    def stack(self) -> Sequence[object]:
        """The stack, or empty where the language has none."""


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
        """Return every next state, or ``None`` when it cannot be forked.

        ``limit`` bounds the outcomes one transition may materialize.
        """


def _unwrap(machine: object, protocol: type[Any], role: str) -> object:
    """Return ``machine``, or the interpreter state a :class:`VM` wraps.

    The protocol is tried before the unwrap, so a raw machine is handed
    back as is.  ``role`` names what the argument failed to be.
    ``protocol`` is ``type[Any]`` with a ``cast`` at each caller: mypy
    refuses a protocol class where ``type[T]`` is expected.
    """
    if isinstance(machine, protocol):
        return machine
    inner = getattr(machine, "_machine", None)
    if isinstance(inner, protocol):
        return inner
    raise TypeError(
        f"{type(machine).__name__} is not {role}: neither it nor any machine "
        "it wraps provides the required members"
    )


def run_until_halt_or_cycle(machine: _StepMachine | VM) -> bool:
    """Step ``machine`` until it halts or revisits an exact state.

    A repeated snapshot *proves* a hang.  ``True`` on a halt, ``False``
    once a cycle is proven; unbounded growth never repeats and is
    :func:`run_until_halt_or_growth`'s.  Brent's algorithm: O(1)
    snapshots, up to ~2x past the cycle's start, so rely on the verdict,
    not the machine's state at detection.
    """
    machine = cast(
        _StepMachine, _unwrap(machine, _StepMachine, "steppable with a snapshot")
    )
    tortoise = machine.snapshot()
    power = 1
    length = 0
    while not machine.halted:
        machine.step()
        length += 1
        # mypy narrows `machine.halted` to Literal[False] from the loop guard
        # and won't re-widen it across `step()`; the explicit local defeats that.
        halted: bool = machine.halted
        if halted:
            return True
        if machine.snapshot() == tortoise:
            return False
        if length == power:
            tortoise = machine.snapshot()
            power *= 2
            length = 0
    return True


def run_until_halt_or_all_branches_cycle(
    machine: _BranchingStepMachine | VM, limit: int = 10_000
) -> bool:
    """Explore random outcomes until one halts or every path is cyclic.

    ``True`` when *some* sequence of draws halts, ``False`` only once the
    reachable graph is finite with no halted state.  ``limit`` bounds
    distinct states and outcomes per step; growth without repeating, or
    an unforkable transition (one reading interactive input), raises
    :class:`TimeoutError`.  Every state is kept, since branches merge.
    A language with no random instruction raises :class:`TypeError`.
    """
    machine = cast(
        _BranchingStepMachine,
        _unwrap(machine, _BranchingStepMachine, "branch-enumerable"),
    )
    pending = [machine.branching_snapshot()]
    seen: set[Hashable] = set()
    while pending:
        state = pending.pop()
        if state in seen:
            continue
        if len(seen) == limit:
            raise TimeoutError(
                f"undecided after {limit} branching states: the reachable "
                "graph may be unbounded"
            )
        seen.add(state)
        if machine.branching_halted(state):
            return True
        successors = machine.branching_successors(state, limit - len(seen))
        if successors is None:
            raise TimeoutError(
                "undecided: a branching transition needs input that cannot "
                "be safely forked"
            )
        pending.extend(successors)
    return False


@runtime_checkable
class _FramedMachine(Protocol):
    """A :class:`_StepMachine` that also exposes its call stack.

    ``frames`` is outermost first; ``frame_entry_key`` is what a frame is
    about to run (function, bindings, input cursor).
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def frames(self) -> Sequence[object]:
        """The live call stack, outermost frame first."""

    def frame_entry_key(self, frame: object) -> Hashable:
        """Return ``frame``'s entry state, hashable and comparable."""


def run_until_halt_or_ancestor(machine: _FramedMachine | VM, limit: int = 64) -> bool:
    """Step ``machine`` until it halts or a call provably replays an ancestor.

    Infinite recursion pushes a frame per step, so the snapshot never
    repeats; instead each pushed frame is compared with those beneath it,
    and an equal ``frame_entry_key`` means it replays what the ancestor is
    still inside.  ``True`` on a halt, ``False`` once such a frame lands.
    The input position carries the soundness (a base case one read away
    would otherwise be called a hang).  Misses bindings that differ every
    lap (``f(x - 1)`` over unbounded ints); O(depth) per push.  ``limit``
    bounds pushes examined -- a repeat shows within a few frames (three
    across the Forbin suite) -- and exhausting it raises
    :class:`TimeoutError`.  No call stack raises :class:`TypeError`.
    """
    machine = cast(_FramedMachine, _unwrap(machine, _FramedMachine, "framed"))
    keys: dict[int, Hashable] = {}
    pushes = 0
    while pushes < limit:
        if machine.halted:
            return True
        depth_before = len(machine.frames)
        machine.step()
        if len(machine.frames) <= depth_before:
            continue
        pushes += 1
        depth = len(machine.frames) - 1
        # A shallower frame at this index belongs to a call that has since
        # returned, so drop it rather than compare against a dead ancestor.
        keys = {d: k for d, k in keys.items() if d < depth}
        keys[depth] = machine.frame_entry_key(machine.frames[-1])
        if keys[depth] in [k for d, k in keys.items() if d < depth]:
            return False
    raise TimeoutError(
        f"undecided after {limit} pushed frames: neither halted nor repeated "
        "an ancestor's entry state"
    )


@runtime_checkable
class _TapeMachine(Protocol):
    """A :class:`_StepMachine` on a rightward-growing tape of cells.

    The four members are what the growth certificate compares across two
    visits to one ``ip``, and together must be the complete state.
    ``tape`` must be the *committed* tape (brainfuck buffers a cell).
    ``ip`` is ``Hashable``: a 2D position includes its heading.
    Opting in claims the language reads and writes only the cell under
    the pointer, is translation-invariant for ``ptr >= 1``, and grows
    rightward by fresh zeros.  Brainfuck, BrainIf, Back, 6-5 and Factor
    qualify; absolute addresses (Suffolk, Minifuck), wrapping or fixed
    tapes (Circlefuck, NoComment, Home Row) and leftward growth (Jaune)
    must not declare it.
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

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


def run_until_halt_or_growth(machine: _TapeMachine | VM, limit: int = 100_000) -> bool:
    """Step ``machine`` until it halts or provably grows without bound.

    ``+[>+]`` grows a cell a lap, so the snapshot is always new.  This
    compares two consecutive visits to one ``ip``; with ``d`` the pointer
    displacement and ``m`` the lowest cell reached between them, a hang
    is written when all of:

    - the input cursor did not move,
    - ``d > 0`` and the tape grew by exactly ``d`` fresh cells,
    - ``m >= 1``, so the period never touched the clamped left edge,
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
    no tape raises :class:`TypeError`.
    """
    machine = cast(_TapeMachine, _unwrap(machine, _TapeMachine, "a tape machine"))
    # The last visit keeps the broad, one-period certificate.  ``origins``
    # proves a steady wave after its first full phase, while ``waves`` is
    # Brent's O(1)-per-position checkpoint for a phase that begins after a
    # transient.  Both minima are updated on every step because the proof
    # is invalid if the period ever reached the clamped left edge.
    last: dict[Hashable, tuple[int, tuple[int, ...], int]] = {}
    lowest: dict[Hashable, int] = {}
    origins: dict[Hashable, tuple[tuple[int, tuple[int, ...], int], int]] = {}
    waves: dict[Hashable, tuple[tuple[int, tuple[int, ...], int], int, int, int]] = {}
    for _ in range(limit):
        if machine.halted:
            return True
        ip, ptr, tape = machine.ip, machine.ptr, machine.tape
        for position in lowest:
            lowest[position] = min(lowest[position], ptr)
        for position, (before, low) in origins.items():
            origins[position] = (before, min(low, ptr))
        for position, (before, low, power, length) in waves.items():
            waves[position] = (before, min(low, ptr), power, length)
        cursor = machine.input_position()
        current = (ptr, tape, cursor)
        previous = last.get(ip)
        if previous is not None and _grows_forever(previous, current, lowest[ip]):
            return False
        last[ip] = current
        lowest[ip] = ptr

        origin = origins.get(ip)
        if origin is None:
            origins[ip] = (current, ptr)
        else:
            before, low = origin
            if _grows_forever(before, current, low):
                return False

        checkpoint = waves.get(ip)
        if checkpoint is None:
            waves[ip] = (current, ptr, 1, 0)
        else:
            before, low, power, length = checkpoint
            # Unreached: by ablation each of the three arms proves every
            # growth program in the suite alone.  Kept -- the corpus is a
            # handful of programs, and an idle arm may decide a shape not
            # yet written.
            if _grows_forever(before, current, low):  # pragma: no cover - see above
                return False
            length += 1
            if length == power:
                waves[ip] = (current, ptr, power * 2, 0)
            else:
                waves[ip] = (before, low, power, length)
        machine.step()
    raise TimeoutError(
        f"undecided after {limit} steps: neither halted nor grew by a "
        "provable translation"
    )


def _grows_forever(
    before: tuple[int, tuple[int, ...], int],
    after: tuple[int, tuple[int, ...], int],
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
class _AffineMachine(Protocol):
    """A machine whose cells grow in *value* on a tape that does not grow.

    Suffolk's ``>>!`` loops stay one to five cells wide while a cell climbs
    by a constant each lap (4501, 9001, 13501), unbounded Python ints.
    ``values`` may grow (compared by subtraction); ``key`` is everything
    else (equality); ``clamp_slack`` is the one place a value changes
    behaviour.  Opting in claims control flow is independent of
    ``values`` (Suffolk has no branch), every operation is affine
    (``acc += tape[ptr]``, ``tape[ptr] + 1 - acc``, resets to 0), and
    every departure is a ``max(0, ...)`` reported by ``clamp_slack``
    *before* the clamping step.  The clamp claim is load-bearing: a slack
    shrinking a little each lap flips after a hundred laps.
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

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
    Bounded values raise :class:`TypeError`: a climbing byte wraps.
    """
    machine = cast(
        _AffineMachine, _unwrap(machine, _AffineMachine, "an affine machine")
    )
    # One slack per step in a single log, and per key the last three steps
    # that visited it, so a lap is a slice rather than a list of its own.
    # Collecting slacks per waiting key would append once for every key
    # still unrevisited -- quadratic on a program whose key never repeats,
    # such as ``>`` alone widening the tape every step.
    slacks: list[int | None] = []
    visits: dict[Hashable, list[tuple[int, tuple[int, ...], int]]] = {}
    for index in range(limit):
        # Suffolk is the only affine machine and never halts, so nothing
        # reaches this return; it stays for the next affine language.
        if machine.halted:  # pragma: no cover - see above
            return True
        slacks.append(machine.clamp_slack)
        key = machine.key
        seen = visits.setdefault(key, [])
        seen.append((index, machine.values, machine.input_position()))
        del seen[:-3]
        if len(seen) == 3 and _climbs_forever(seen, slacks):
            return False
        machine.step()
    raise TimeoutError(
        f"undecided after {limit} steps: neither halted nor climbed by a "
        "provable affine step"
    )


def _climbs_forever(
    visits: list[tuple[int, tuple[int, ...], int]],
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


def run_until_halt(
    machine: _SteppableMachine | VM,
    limit: int | None = None,
    *,
    stop: Callable[[], bool] | None = None,
) -> bool:
    """Step ``machine`` until it halts, or the budget or ``stop`` ends it.

    Proves nothing: ``True`` halted, ``False`` still going.  ``limit`` in
    steps, ``None`` unbounded.  ``stop`` is checked *before* each step
    (what a breakpoint means).  The machine is left where it stopped.
    """
    steps = 0
    while not machine.halted:
        if stop is not None and stop():
            return False
        if limit is not None and steps == limit:
            return False
        machine.step()
        steps += 1
    return True


@runtime_checkable
class VM(Protocol):
    """A step-capable interpreter wrapper.

    ``ip``/``memory``/``stack`` are language-shaped.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    def snapshot(self) -> Hashable:
        """Return the internal state cycle detection compares, hashable.

        ``output`` is excluded (the post-halt dump writes on seven
        languages): equal internal state means the same future.
        """

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def output(self) -> str:
        """Everything the machine has written so far."""

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The current code/instruction position, language-shaped.

        An index, a coordinate tuple, or ``None`` once the agent is
        consumed.  The tuple's arity is not stable within a run: six
        languages change shape (Flowchart and Super SNUSP to ``None``,
        ``function x(y)`` to ``()``, APL, Forþ and COD growing and
        shrinking -- COD through 4, 8, 12, 16 to 0), so size nothing to
        the initial arity; :meth:`~esolangs.debugger.Debugger.break_at`
        checks kind, not arity.  For the ten grid languages the leading
        components are row then column, never x then y; nine more report
        a tuple without being grids (3D Brainfuck, Back, Eval, Forþ,
        Grapheme, Interprogck8, APL, Forbin, ``function x(y)``) and
        ``describe(...)["state_model"]`` separates them.
        """

    @property
    def memory(self) -> list[int]:
        """The addressable cells, or ``[]`` where there is no such store."""

    @property
    def stack(self) -> list[object]:
        """The stack, or ``[]`` where the language has none."""

    @property
    def ip_shape(self) -> str:
        """How to read :attr:`ip` as a place in the source, if at all.

        ``"offset"`` (default) counts characters; ``"grid"`` is row, column,
        then heading; ``"line"`` starts with a line number; ``"opaque"`` is
        a real position that is not a place in the source.  Every tuple
        ``ip`` declares one of the last three
        (``test_a_positional_ip_says_what_it_counts``): a frame stack
        (Forth, Grapheme, Forbin), a depth and cursor (Eval) or a 3-D point
        (3D Brainfuck) all look like ``(row, col)``.
        """

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        """The machine's own named state, as ``(name, text)`` pairs.

        The property descriptors on the machine's class, less
        :data:`_NOT_A_VIEW`, so they cannot drift from the interpreters.
        Two names reading one slot (``ind`` and ``ip``) are both shown.
        """

    @property
    def self_halts(self) -> bool:
        """Whether the program can reach a halt of its own.

        ``False`` where the *language* has no halt: bound the run.  It
        does not promise a program runs forever -- Suffolk ends when a read runs out of
        input (757 steps on a generated table program), A Painter Ant does
        run forever.  No tally of carriers here; ``[n for n in
        list_languages() if describe(n)["self_halts"]]`` cannot drift.
        """

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        """Whether the output arrives on the step *after* the halt.

        A caller stopping at ``halted`` holds ``""``; one more ``step()``
        writes what ``run`` writes.
        """

    @property
    def eof_is_a_value(self) -> bool:
        """Whether a read past the end of the input yields a value here.

        The norm raises :class:`~esolangs.exceptions.InputExhaustedError`;
        ``True`` marks the languages that take a value instead, so an
        underfed program answers a different row.  Two are neither: Alight
        is ``True`` but halts on ``cannot apply '+' to 2.0 and 'eof'``;
        Suffolk is ``False`` but the read *ends* the program.  Swept one
        line short: of 52 languages reading stdin, 44 of 45 ``False`` raise
        and 6 of 7 ``True`` answer a different row with
        :class:`~esolangs.exceptions.InputMismatchWarning`.
        """

    @property
    def steppable_to_answer(self) -> bool:
        """Whether stepping this language ever reaches the answer.

        ``False`` for A Painter Ant alone: the answer is the render after
        the walk is proven periodic (three million steps leave ``output``
        empty).  Distinct from ``self_halts``, which Suffolk carries while
        still writing its answer.  Use :func:`esolangs.run`.
        """


#: The names a caller already has by other means -- the views every language
#: offers, the snapshot hooks the cycle provers use, and the traits -- so
#: they are not repeated as "the machine's own".
_NOT_A_VIEW = frozenset(
    {
        "ip",
        "memory",
        "stack",
        "output",
        "halted",
        "snapshot",
        "branching_snapshot",
        "branching_halted",
        "branching_successors",
        "frame_entry_key",
        "self_halts",
        "steppable_to_answer",
        "dumps_on_the_post_halt_step",
        "eof_is_a_value",
        "ip_shape",
        "reproducible_seed",
    }
)

#: How many items of a sequence view to show before counting the rest.  A
#: tape can be thousands of cells, and rendering one per step would cost
#: more than running the program.
_VIEW_ITEMS = 8


def _read_view(machine: object, name: str) -> str | None:
    """Return ``machine.name`` as short text, or ``None`` if it cannot be read.

    ``None`` so one property raising before a run does not take the set down.
    """
    try:
        value = getattr(machine, name)
    except Exception:
        return None
    return _abbreviate(value)


def _abbreviate(value: object) -> str:
    """Render ``value`` short enough to sit on one row.

    Cut *before* formatting: a 4000-cell tape formatted then truncated would
    be the stepper's most expensive step.
    """
    if isinstance(value, (list, tuple)) and len(value) > _VIEW_ITEMS:
        return f"{type(value)(value[:_VIEW_ITEMS])!r} +{len(value) - _VIEW_ITEMS} more"
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


class _DelegatingVM:
    """A VM for an interpreter that describes its own shape.

    Subclasses provide ``__init__``; everything else forwards, and
    ``output`` is captured here.  ``memory`` and ``stack`` are copied out
    so a caller cannot write into a running machine.
    """

    _machine: _StepMachineWithShape

    def __init__(self, stdin: str = "") -> None:
        """Create the input stream every subclass's machine reads from.

        The program is not taken here: each subclass hands it to its machine.
        """
        self._io = ScriptedIO(stdin)

    @property
    def output(self) -> str:
        return self._io.getvalue()

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        """Execute one instruction, translating what the interpreter raises.

        The same promise as :func:`esolangs.run`: a bare ``ValueError``
        becomes :class:`~esolangs.exceptions.ProgramError`, a
        ``RecursionError`` :class:`~esolangs.exceptions.InterpreterLimitError`.
        """
        try:
            self._machine.step()
        except RecursionError as exc:
            raise InterpreterLimitError(
                f"the {type(self).__name__} interpreter recursed deeper than "
                f"CPython's stack limit allows on this program"
            ) from exc
        except ProgramError:
            raise
        except ValueError as exc:
            raise ProgramError(str(exc)) from exc

    def snapshot(self) -> Hashable:
        """Return the underlying machine's complete state."""
        return self._machine.snapshot()

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        return self._machine.ip

    @property
    def memory(self) -> list[int]:
        return list(self._machine.memory)

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)

    # The traits come off the machine by ``getattr``, the way
    # ``reproducible_seed`` does: they are facts about the language, so the
    # interpreter declares them and the fifty-odd following the common shape
    # say nothing.  The defaults are that common case.

    @property
    def self_halts(self) -> bool:
        return bool(getattr(self._machine, "self_halts", True))

    @property
    def ip_shape(self) -> str:
        return str(getattr(self._machine, "ip_shape", "offset"))

    @property
    def views(self) -> tuple[tuple[str, str], ...]:
        machine = self._machine
        found = []
        for name, attribute in sorted(vars(type(machine)).items()):
            if name.startswith("_") or name in _NOT_A_VIEW:
                continue
            if not isinstance(attribute, property):
                continue
            text = _read_view(machine, name)
            if text is not None:
                found.append((name, text))
        return tuple(found)

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        return bool(getattr(self._machine, "dumps_on_the_post_halt_step", False))

    @property
    def steppable_to_answer(self) -> bool:
        return bool(getattr(self._machine, "steppable_to_answer", True))

    @property
    def eof_is_a_value(self) -> bool:
        return bool(getattr(self._machine, "eof_is_a_value", False))


def _derived_adapter(language: str) -> Callable[[str, str], _DelegatingVM]:
    """Build the adapter for a language whose wrapper is pure boilerplate.

    Only the module and text-vs-lines differ, both already in ``RUNNERS``;
    every registered language goes through here.
    """
    module_path, split = RUNNERS[language]
    # Bound to another name first: a class body cannot read the enclosing
    # function's ``language`` while binding a class attribute of that name.
    display_name = language

    class _Derived(_DelegatingVM):
        #: The registry's display name for this adapter's language.
        #:
        #: ``_DelegatingVM`` never sees a name, and the debugger needs one
        #: to ask ``describe`` whether a read past the end of input is a
        #: value here -- the difference between a wrong answer and a raise.
        language = display_name

        def __init__(self, program: str, stdin: str = "") -> None:
            super().__init__(stdin)
            import importlib
            import inspect

            from esolangs.interpreters.randomness import Seeded

            module = importlib.import_module(f"esolangs.interpreters.{module_path}")
            code = program.splitlines() if split else program
            # ``_Machine`` is private to its module but is the state object
            # this whole file is built around.
            state = getattr(module, "_Machine")  # noqa: B009
            # Seeded for reproducibility (the interpreter falls back to
            # ``secrets``); the seed is the machine's, since the first draw
            # is a fact about the language (COD goes East, LaserFuck up).
            if "rng" in inspect.signature(state).parameters:
                seed = getattr(state, "reproducible_seed", 0)
                self._machine = state(code, self._io, rng=Seeded(seed))
            else:
                self._machine = state(code, self._io)

    _Derived.__name__ = _Derived.__qualname__ = f"_{language}VM"
    _Derived.__doc__ = f"Adapter for {language}; the interpreter describes its shape."
    return _Derived


# Language name -> VM adapter, read off ``RUNNERS`` rather than listed
# again, so an unregistered name is the only thing raising
# UnknownLanguageError.  Building an adapter imports nothing; the
# interpreter is imported inside its ``__init__``.  Typed as the factory it
# is used as rather than as the base class, which takes only the input.
_VM_ADAPTERS: dict[str, Callable[[str, str], _DelegatingVM]] = {
    name: _derived_adapter(name) for name in RUNNERS
}


@cache
def machine_traits(language: str) -> dict[str, bool]:
    """Return ``language``'s driving traits without running anything.

    Read off the state *class*, so :func:`esolangs.describe` needs no program.
    """
    import importlib

    # No membership check beyond ``resolve``: it only returns registry
    # names, and the registry and ``RUNNERS`` hold the same 65.
    name = resolve(language)
    module = importlib.import_module(f"esolangs.interpreters.{RUNNERS[name][0]}")
    state = getattr(module, "_Machine")  # noqa: B009
    return {
        "self_halts": bool(getattr(state, "self_halts", True)),
        "dumps_on_the_post_halt_step": bool(
            getattr(state, "dumps_on_the_post_halt_step", False)
        ),
        "steppable_to_answer": bool(getattr(state, "steppable_to_answer", True)),
        "eof_is_a_value": bool(getattr(state, "eof_is_a_value", False)),
    }


def make_vm(language: str, program: str | os.PathLike[str], stdin: str = "") -> VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    ``stdin`` is fed line by line; the name resolves case-insensitively via
    :func:`~esolangs.registry.resolve`, and only a name outside the registry
    raises :class:`UnknownLanguageError`.  The program and ``stdin`` are
    checked as :func:`esolangs.run` checks them (an unfilled template
    otherwise runs to a confident ``'0'``), and the checked value is what
    reaches the interpreter (:mod:`esolangs._validate`).
    """
    from esolangs import check_program

    name = resolve(language)
    if name not in _VM_ADAPTERS:
        raise UnknownLanguageError(language)
    source = check_program(name, program, stdin)
    try:
        return _VM_ADAPTERS[name](source, stdin)
    except RecursionError as exc:
        raise InterpreterLimitError(
            f"the {name} interpreter recursed deeper than CPython's stack "
            f"limit allows while loading this program "
            f"({len(source)} characters)"
        ) from exc
    except ProgramError:
        raise
    except ValueError as exc:
        # Most interpreters parse in their constructor and signal a
        # malformed program with a plain ``ValueError``, which ``run``
        # re-raises as ``ProgramError``.
        raise ProgramError(str(exc)) from exc
