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
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from typing import Protocol, runtime_checkable

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


def run_until_halt_or_cycle(machine: _StepMachine) -> bool:
    """Step ``machine`` until it halts or revisits an exact state.

    A deterministic machine that revisits its complete internal state has
    looped forever, so a repeated snapshot is a *proof* of a hang that is
    reported immediately instead of waiting out a wall-clock timeout.
    Returns ``True`` when the machine halts and ``False`` once a cycle is
    proven.  It catches *cycles*, not every hang — an unbounded-growth loop
    never revisits a state, so callers keep a timeout as the backstop for
    that class.

    Uses Brent's cycle-detection algorithm: O(1) snapshots held at once
    (one "tortoise" checkpoint compared against the live machine's state on
    every step) instead of a hash set of every state visited, at the cost of
    stepping up to ~2x further past the cycle's start before ``False`` is
    returned — callers must not rely on the machine's state at the moment
    of detection, only on the True/False verdict.
    """
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


def run_until_halt_or_ancestor(machine: _FramedMachine, limit: int = 64) -> bool:
    """Step ``machine`` until it halts or a call provably replays an ancestor.

    :func:`run_until_halt_or_cycle` cannot catch infinite recursion: a call
    that never returns pushes one frame per step and pops none, so the
    machine's whole-state snapshot grows forever and never repeats.  That is
    the unbounded-growth class, and it is why recursive languages keep a
    wall-clock backstop -- one that deadlocks under ``pytest --cov`` (see
    ``docs/walls.md``).

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
    """
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
class VM(Protocol):
    """A step-capable interpreter wrapper.

    ``ip``/``memory``/``stack`` are language-shaped: each adapter exposes
    what the language's state actually is, so a tape language's ``memory``
    is its cells, a stack language's ``stack`` its values, and so on.
    """

    def step(self) -> None:
        """Execute one command, advancing the machine."""

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

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        return self._machine.ip

    @property
    def memory(self) -> list[int]:
        return list(self._machine.memory)

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)


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
    ``of``/``rng`` handling below, so no per-language code is left.
    """
    module_path, split, _ = RUNNERS[language]

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
            # Some state objects cannot take a program positionally -- a
            # dataclass whose parsed field is ``init=False``, or one whose
            # code field sits behind ``io``.  Those offer ``of(code, io)``
            # instead, which is the same construction under a name.  A
            # state class may also use ``of`` for one of the language's own
            # names (AddSubJump's overflow flag is a property), so only a
            # callable ``of`` counts as the constructor.
            state = getattr(module, "_Machine", None) or module.State
            of = getattr(state, "of", None)
            machine = of if callable(of) else state
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
            if "rng" in inspect.signature(machine).parameters:
                seed = getattr(state, "reproducible_seed", 0)
                self._machine = machine(code, self._io, rng=Seeded(seed))
            else:
                self._machine = machine(code, self._io)

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
