"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps one of the step-capable interpreters in a :class:`VM`
that exposes the run state between commands: ``step()`` executes one command,
and the ``halted``/``output``/``ip``/``memory``/``stack`` properties describe
the machine after it.  The fields are language-shaped rather than uniform:
a tape language exposes its cells and code cursor, an OISC its cells and
instruction pointer, and a stack language its stack (empty ``stack`` where a
language has none).

Every registered interpreter exposes a ``step()``/``halted`` state object,
so every language in the registry can be wrapped; only an unregistered name
is refused.

Two of the languages' conventions defeat the obvious driving loop, so the
:class:`VM` reports them rather than leaving a caller to find out:
``self_halts`` is ``False`` where ``halted`` never becomes true, and
``dumps_on_the_post_halt_step`` is ``True`` where the output is written on
the step after the halt.  ``while not vm.halted: vm.step()`` hangs on the
first group and returns ``""`` on the second, and neither is discoverable
from the protocol alone.  A hang detector below is the other way to drive
the first group, and takes the bound off the caller entirely.

The four hang detectors here -- :func:`run_until_halt_or_cycle`,
:func:`run_until_halt_or_all_branches_cycle`,
:func:`run_until_halt_or_ancestor`, and :func:`run_until_halt_or_growth` --
each take either a :class:`VM` or the interpreter state one wraps, so
proving a hang needs nothing more than :func:`make_vm`.  What a detector
needs beyond stepping is a *sub*-protocol that only some languages have: a
call stack to compare frames across, enumerable random outcomes to fork, or
a growing tape.  A language lacking one raises :class:`TypeError` rather
than being handed a verdict about state it does not keep.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from typing import Any, Protocol, cast, runtime_checkable

from esolangs.exceptions import UnknownLanguageError
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import RUNNERS


@runtime_checkable
class _StepMachine(Protocol):
    """The minimal step-capable surface the hang detector steps on.

    ``snapshot()`` must return a hashable tuple of the machine's *complete*
    internal state — including the input cursor — or a "repeat" is not a
    real cycle.
    """

    def step(self) -> None:
        """Execute one instruction, advancing the machine."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    def snapshot(self) -> Hashable:
        """Return the complete internal state, hashable for cycle detection."""


@runtime_checkable
class _StepMachineWithShape(_StepMachine, Protocol):
    """A step-capable machine that also describes its own VM shape.

    The three members are the ones :class:`VM` exposes; an interpreter that
    defines them can be wrapped by :class:`_DelegatingVM` without any
    per-language code in this module.

    They are ``Sequence``, not ``list``, and that is what makes the
    interpreter free to expose its store *directly*.  ``list`` is invariant,
    so a machine holding ``self.stack: list[int]`` -- which several do, under
    exactly this name -- could never satisfy a ``list[object]`` member, and
    could not add a converting property either, because the attribute is the
    name.  ``Sequence`` is covariant, so the live attribute satisfies it as
    it stands, and :class:`_DelegatingVM` materializes the ``list`` that
    :class:`VM` promises.

    That also puts the fresh-copy contract in one place.  A caller must not
    be able to reach back into a machine through ``vm.memory``, and the
    copy that guarantees it belongs at the boundary that owes it rather
    than in every interpreter.
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

    The state is deliberately an immutable value rather than the live
    machine.  Exploring one outcome must not consume a random draw, input,
    or output that belongs only to a sibling outcome.
    """

    def branching_snapshot(self) -> Hashable:
        """Return the initial complete state for a branching search."""

    def branching_halted(self, state: Hashable) -> bool:
        """Whether ``state`` has halted."""

    def branching_successors(
        self, state: Hashable, limit: int
    ) -> Sequence[Hashable] | None:
        """Return every next state, or ``None`` when it cannot be forked.

        ``limit`` bounds the outcomes this one transition may materialize.
        A public machine step can itself repeat a random instruction.
        """


def _unwrap(machine: object, protocol: type[Any], role: str) -> object:
    """Return ``machine``, or the interpreter state a :class:`VM` wraps.

    The detectors were written against the interpreters' ``_Machine``
    classes, so every caller reached past :func:`make_vm` and hand-built
    one -- the private class, its ``ScriptedIO``, and for a random language
    the seeded generator, all restated at the call site.  A :class:`VM`
    already holds exactly that machine, constructed exactly that way, so
    accepting one and opening it here removes the reason to import a
    private name.

    The protocol is tried *before* the unwrap, so a raw machine is handed
    straight back and a wrapper is opened only when it is not itself what
    the detector needs.  That order is also what keeps
    :func:`run_until_halt_or_cycle` stepping the object it was given: a
    :class:`VM` forwards ``step``/``halted``/``snapshot`` and so already
    satisfies :class:`_StepMachine`, which is why passing one there worked
    before this function existed and must keep meaning the same thing.

    ``role`` names what the argument failed to be, because the interesting
    failure is not "wrong type" but "this language has no such thing": a
    machine without ``frames`` does not recurse, and one without
    ``branching_successors`` has no random instruction to fork.

    ``protocol`` is ``type[Any]`` and the result is narrowed by a ``cast``
    at each caller, rather than the ``TypeVar`` this shape invites: mypy
    refuses a protocol class where a ``type[T]`` is expected
    (``type-abstract``), since a protocol cannot be instantiated.  The
    ``isinstance`` below is the real check either way.
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

    A deterministic machine that revisits its complete internal state has
    looped forever, so a repeated snapshot is a *proof* of a hang that is
    reported immediately instead of waiting out a wall-clock timeout.
    Returns ``True`` when the machine halts and ``False`` once a cycle is
    proven.  It catches *cycles*, not every hang — an unbounded-growth loop
    never revisits a state.  On a tape language,
    :func:`run_until_halt_or_growth` proves that class instead; elsewhere
    callers keep a timeout as the backstop for it.

    Uses Brent's cycle-detection algorithm: O(1) snapshots held at once
    (one "tortoise" checkpoint compared against the live machine's state on
    every step) instead of a hash set of every state visited, at the cost of
    stepping up to ~2x further past the cycle's start before ``False`` is
    returned — callers must not rely on the machine's state at the moment
    of detection, only on the True/False verdict.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.
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

    Returns ``True`` when *some* sequence of random draws halts.  Returns
    ``False`` only after the complete reachable state graph is finite and
    contains no halted state, proving that every sequence of draws runs
    forever.  The latter is the useful extension of
    :func:`run_until_halt_or_cycle` for a random branch: revisiting a state
    on one outcome alone says nothing when another outcome could escape.

    ``limit`` bounds distinct states and the outcomes one public step may
    materialize.  A machine that grows a tape, stack, or other state without
    repeating remains undecided, as does a transition that cannot be forked
    (for example, one that would read future interactive input).  Both raise
    :class:`TimeoutError` rather than being mistaken for a universal hang.
    The search keeps every exact state it has seen, unlike Brent's O(1)
    deterministic detector, because branches can merge after taking
    different random choices.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.  A language with no random
    instruction has no branching surface to search and raises
    :class:`TypeError` rather than being reported as a hang.
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

    ``frames`` is the live stack, outermost first, and ``frame_entry_key``
    returns what a frame is *about to run* -- its function, its bindings,
    and the input cursor -- so two frames with equal keys will replay each
    other.  Separate from :class:`_StepMachine` because the cycle detector
    needs neither.
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

    :func:`run_until_halt_or_cycle` cannot catch infinite recursion: a call
    that never returns pushes one frame per step and pops none, so the
    machine's whole-state snapshot grows forever and never repeats.  That is
    the unbounded-growth class -- the same one
    :func:`run_until_halt_or_growth` handles on a tape, where the growing
    state is cells rather than frames -- and it is why recursive languages
    keep a wall-clock backstop, one that deadlocks under ``pytest --cov``
    (see ``docs/walls.md``).

    This is the narrower check that class allows.  Rather than comparing
    whole-machine states across time, it compares each newly-pushed frame
    against the frames already beneath it: if a frame enters the same
    function, with the same bindings, at the same input position as an
    ancestor, it is about to replay exactly what that ancestor is still in
    the middle of, and the recursion cannot terminate.  Returns ``True``
    when the machine halts and ``False`` once such a frame is pushed.

    The input position is part of the key and carries the soundness.  A
    recursion whose base case depends on a byte it has yet to read enters
    with identical bindings every lap and would otherwise be called a hang
    while it is one read away from returning.

    Two things this does not do.  It does not catch every infinite
    recursion -- one whose bindings genuinely differ every lap (``f(x - 1)``
    over unbounded integers) never repeats a key, so callers keep the
    wall-clock backstop for that class.  And it costs O(depth) per push
    rather than the cycle detector's O(1), which is affordable only because
    it runs once per *call*, not once per step.

    ``limit`` bounds the walk in *pushes examined*, not steps, and 64 is
    generous: a repeat that exists at all shows up within a few frames --
    three, for every case the Forbin suite covers -- because the key does
    not vary with how long the program has been running.  Exhausting it
    raises :class:`TimeoutError` rather than returning a verdict, so a
    program the check cannot decide is never silently reported as halting.
    That distinction is what keeps the bound cheap: a caller need not leave
    headroom "just in case", and a mutant that defeats the early return
    fails a test in milliseconds instead of walking ten thousand steps of
    live recursion.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.  A language with no call stack
    cannot recurse and raises :class:`TypeError` rather than reporting a
    verdict about frames it does not have.
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
    visits to one code position.  ``tape`` must be the *committed* tape --
    brainfuck buffers the cell under the pointer, and a logical state with
    two spellings would break the comparison exactly as it would break the
    cycle detector's hash.  ``input_position`` is the input cursor, and it
    carries the soundness the same way ``frame_entry_key``'s does.

    ``ip`` is the language-shaped code position every machine here already
    exposes, and it is only ever used as a dictionary key, never
    arithmetically -- so it is ``Hashable`` rather than ``int``.  That is
    deliberate.  A 2D language's position is a tuple that includes the
    heading, and *must* be: two visits to one grid cell travelling in
    different directions are not the same point in the program, and keying
    on the coordinates alone would compare them as if they were.  Taking
    the machine's own ``ip`` gets that right by construction instead of by
    remembering it per language.

    Together, ``ip``, ``ptr``, ``tape`` and ``input_position`` must be the
    machine's *complete* state -- the same completeness ``snapshot``
    promises the cycle detector.  A register or flag living outside them
    would let two compared visits differ in something the certificate never
    looked at, and the replay argument would not hold.

    Opting in is also a claim about the language, not just about the
    members:

    - a transition reads and writes only the cell under the pointer,
    - the semantics are translation-invariant for ``ptr >= 1`` -- moving
      the whole configuration one cell right changes nothing, which fails
      only at the clamped left edge,
    - the tape grows rightward, by fresh zero cells.

    Brainfuck, BrainIf, Back, 6-5 and Factor satisfy all three.  A language
    with absolute cell addresses (Suffolk's ``<`` resets the pointer to 0,
    Minifuck reads cells 0-7 by index), a wrapping or fixed-size tape
    (Circlefuck, NoComment, Home Row), or leftward growth (Jaune prepends,
    which shifts every existing index) does not, and must not declare this
    protocol -- matching member names is not eligibility.
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

    :func:`run_until_halt_or_cycle` cannot catch ``+[>+]``.  The tape gets
    one cell longer and the pointer one cell further right every lap, so
    the whole-machine snapshot is new every time and Brent's detector never
    sees a repeat -- that is the unbounded-growth class its docstring hands
    back to a wall-clock timeout.

    This is the check that class allows on a tape.  Instead of comparing
    whole states, it compares two consecutive visits to the *same code
    position* -- the machine's own ``ip``, so a 2D language's heading is
    part of it -- and asks whether the second is the first shifted right.
    Let
    ``d`` be the pointer's displacement between the visits, ``m`` the
    lowest cell the pointer reached in between, and write a hang when all
    of:

    - the input cursor did not move (a ``,`` in the period makes the next
      lap input-dependent, so it is undecided, not a hang),
    - ``d > 0`` and the tape grew by exactly ``d`` fresh cells,
    - ``m >= 1``, so the period never touched the clamped left edge,
    - ``tape2[i + d] == tape1[i]`` for every ``m <= i < len(tape1)``.

    Together those make the second visit's configuration, restricted to the
    cells at or right of ``m``, the first's translated by ``d``.  Since the
    machine reads only the cell under the pointer and its semantics are
    translation-invariant away from the left edge, the period must replay
    at ``+d``, and then again at ``+2d``, forever: an induction, not a
    guess.  Returns ``True`` when the machine halts and ``False`` once such
    a certificate is found.

    Three details that are the whole soundness argument.  ``m >= 1`` is
    what licenses translation: a period that touched cell 0 may have been
    clamped by ``<`` where its shifted copy would not be, and the two would
    diverge.  The lower bound ``i >= m`` rather than ``i >= 0`` is what
    makes ``+[>++]`` provable -- its cell 0 keeps the value 1 while the
    interior fills with 2s, so a full-width shift never matches, while the
    suffix from the period's own minimum does; cells left of ``m`` are
    unreachable for the rest of the run, so their disagreeing is not a
    counterexample.  And the length check is what rules out a shift that
    merely *looks* aligned: the fresh cells must be exactly the ``d`` zeros
    the growth created.

    Two things this does not do.  It compares *consecutive* visits to a
    position, so growth whose period spans two visits stays undecided --
    like the ancestor detector's ``f(x - 1)``, a real gap, left to the
    caller's timeout.  And ``d == 0`` is not its business: a loop that
    grows a cell's value rather than the tape, such as ``+[<+]``, revisits
    an exact state once the value wraps at 256 and is
    :func:`run_until_halt_or_cycle`'s to prove.

    ``limit`` bounds the walk in steps.  Exhausting it raises
    :class:`TimeoutError` rather than returning a verdict, so a program
    this cannot decide is never reported as halting.

    Takes either a raw interpreter state or a :class:`VM` from
    :func:`make_vm`; see :func:`_unwrap`.  A language with no tape has
    nothing to grow and raises :class:`TypeError` rather than a verdict.
    """
    machine = cast(_TapeMachine, _unwrap(machine, _TapeMachine, "a tape machine"))
    # Per code position: the last visit's (pointer, tape, input cursor),
    # and the lowest pointer seen since that visit.  One entry per position
    # rather than per state, so this is bounded by the program's length.
    last: dict[Hashable, tuple[int, tuple[int, ...], int]] = {}
    lowest: dict[Hashable, int] = {}
    for _ in range(limit):
        if machine.halted:
            return True
        ip, ptr, tape = machine.ip, machine.ptr, machine.tape
        for position in lowest:
            if ptr < lowest[position]:
                lowest[position] = ptr
        cursor = machine.input_position()
        previous = last.get(ip)
        if previous is not None and _grows_forever(
            previous, (ptr, tape, cursor), lowest[ip]
        ):
            return False
        last[ip] = (ptr, tape, cursor)
        lowest[ip] = ptr
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
    """Whether ``after`` is ``before`` translated right by the growth.

    The certificate itself, split out so the four conditions read as the
    list in :func:`run_until_halt_or_growth`'s docstring rather than as one
    expression buried in a loop.
    """
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
class VM(Protocol):
    """A step-capable interpreter wrapper.

    ``ip``/``memory``/``stack`` are language-shaped: each adapter exposes
    what the language's state actually is, so a tape language's ``memory``
    is its cells, a stack language's ``stack`` its values, and so on.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

    def snapshot(self) -> Hashable:
        """Return the complete state used by cycle detection."""

    @property
    def halted(self) -> bool:
        """Whether the machine has finished executing."""

    @property
    def output(self) -> str:
        """Everything the machine has written so far."""

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The current code/instruction position, or (position, direction).

        A linear language's ``ip`` is an index into its program; a 2D
        language's is the moving agent's ``(x, y, heading)``; a language
        whose agent has been consumed reports ``None``.
        """

    @property
    def memory(self) -> list[int]:
        """The addressable cells, or ``[]`` where there is no such store."""

    @property
    def stack(self) -> list[object]:
        """The stack, or ``[]`` where the language has none."""

    @property
    def self_halts(self) -> bool:
        """Whether the program can reach a halt of its own.

        ``False`` for the two languages whose ``halted`` is always
        ``False`` -- A Painter Ant and Suffolk -- so the obvious
        ``while not vm.halted: vm.step()`` never returns on them.  A
        caller driving one has to bound the run itself: a hang detector
        above, or :func:`esolangs.run`'s ``timeout``.
        """

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        """Whether the output arrives on the step *after* the halt.

        ``True`` for the four languages whose ``run`` ends its loop with
        one more ``step()`` to dump the final tape or registers.  A caller
        that stops at ``halted`` has driven such a program correctly and
        still holds ``""``; one further ``step()`` writes what ``run``
        writes, and the no-op step is the one after that.
        """


class _DelegatingVM:
    """A VM for an interpreter that describes its own shape.

    The language-shaped mapping -- ``ip``/``memory``/``stack``, genuinely
    different for all 63 of them -- lives on each interpreter's
    ``_Machine`` rather than here, in a file that does not otherwise know
    the languages.  Keeping it next to the state it describes leaves the
    adapter with the one thing that really is per-language: how the machine
    is constructed.  Subclasses provide ``__init__`` only; everything else
    forwards, and ``output`` is captured here.

    ``memory`` and ``stack`` are copied on the way out.  The machine may
    hand back its live store -- several expose the list itself, under
    exactly these names -- and a caller holding ``vm.memory`` must not be
    able to write into a running machine through it.  Copying here rather
    than in each interpreter keeps that guarantee in one place, and turns
    the widening from ``Sequence`` into the ``list`` :class:`VM` promises.
    """

    _machine: _StepMachineWithShape

    def __init__(self, program: str | list[str], stdin: str = "") -> None:
        """Create a VM for ``program`` reading input from ``stdin``."""
        self._io = ScriptedIO(stdin)
        self._program = program

    @property
    def output(self) -> str:
        return self._io.getvalue()

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

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

    # The two language conventions a stepping caller cannot discover for
    # itself: that a language never halts, and that its output lands one
    # step past the halt.  Both come off the machine by ``getattr``, the
    # way ``reproducible_seed`` does, and for the same reason -- they are
    # facts about the language, so the interpreter says so and the fifty-odd
    # that follow the common shape declare nothing.
    #
    # The defaults are the common case, which is why the traits are spelled
    # positively on the machines that carry them: a language that says
    # nothing self-halts and writes before it does.

    @property
    def self_halts(self) -> bool:
        return bool(getattr(self._machine, "self_halts", True))

    @property
    def dumps_on_the_post_halt_step(self) -> bool:
        return bool(getattr(self._machine, "dumps_on_the_post_halt_step", False))


def _derived_adapter(language: str) -> type[_DelegatingVM]:
    """Build the adapter for a language whose wrapper is pure boilerplate.

    Once an interpreter describes its own shape, most adapters differ only
    in which module to import and whether the program is passed as text or
    as lines -- and ``RUNNERS`` already records both, because ``run`` needs
    exactly the same two facts.  Deriving from it means the adapter set
    cannot drift from the runner set, and adding a language that follows
    the common shape needs no code here at all.

    Every registered language now goes through here.  The exceptions that
    once kept a hand-written class -- extra setup, an overridden ``step()``,
    a construction disagreeing with the runner's -- were absorbed by the
    common constructor and ``rng`` handling below, so no per-language code
    is left.
    """
    module_path, split = RUNNERS[language]

    class _Derived(_DelegatingVM):
        def __init__(self, program: str, stdin: str = "") -> None:
            super().__init__(program, stdin)
            import importlib
            import inspect

            from esolangs.interpreters.randomness import Seeded

            module = importlib.import_module(f"esolangs.interpreters.{module_path}")
            code = program.splitlines() if split else program
            # ``_Machine`` is private to its module but is the state object
            # this whole file is built around; the explicit adapters below
            # import it by name for the same reason.
            state = getattr(module, "_Machine")  # noqa: B009
            # A language with a random instruction takes a source for it,
            # and a stepped VM has to be reproducible, so one is passed
            # wherever it is accepted.  It is optional exactly like ``io``
            # is: the interpreter falls back to ``secrets`` without it.
            #
            # The seed comes from the machine.  Which draw a language
            # wants to start from is a fact about that language -- COD's
            # own junction example goes East, LaserFuck's grids are
            # written for a laser heading up -- so the interpreter says
            # so, rather than every caller having to know.
            if "rng" in inspect.signature(state).parameters:
                seed = getattr(state, "reproducible_seed", 0)
                self._machine = state(code, self._io, rng=Seeded(seed))
            else:
                self._machine = state(code, self._io)

    _Derived.__name__ = _Derived.__qualname__ = f"_{language}VM"
    _Derived.__doc__ = f"Adapter for {language}; the interpreter describes its shape."
    return _Derived


# Language name -> VM adapter.  Every registered language is step-capable,
# so every one gets a derived adapter and an unregistered name is the only
# thing that raises UnknownLanguageError.  The set is read off ``RUNNERS``
# rather than listed again here: a second copy of sixty-three names is a
# second thing to keep in step, and
# ``test_every_registry_language_has_a_vm_adapter`` existed only to catch
# the two drifting apart.  Building an adapter imports nothing -- the
# interpreter is imported inside the adapter's ``__init__`` -- so this
# stays as lazy as the hand-written table was.
_VM_ADAPTERS: dict[str, type[_DelegatingVM]] = {
    name: _derived_adapter(name) for name in RUNNERS
}


def make_vm(language: str, program: str, stdin: str = "") -> VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    The wrapper exposes ``step()``, ``halted``, ``output``, ``ip``,
    ``memory``, and ``stack`` between commands.  ``stdin`` is fed to the
    program line by line, like :func:`esolangs.run`.  Every registered
    language is step-capable, so only a name outside the registry raises
    :class:`UnknownLanguageError`.
    """
    if language not in _VM_ADAPTERS:
        raise UnknownLanguageError(language)
    return _VM_ADAPTERS[language](program, stdin)
