"""A step-and-inspect interface for the interpreter suite.

:func:`make_vm` wraps one of the step-capable interpreters in a :class:`VM`
that exposes the run state between commands: ``step()`` executes one command,
and the ``halted``/``output``/``ip``/``memory``/``stack`` properties describe
the machine after it.  The fields are language-shaped rather than uniform:
a tape language exposes its cells and code cursor, an OISC its cells and
instruction pointer, and a stack language its stack (empty ``stack`` where a
language has none).

The interpreters whose state objects expose ``step()``/``halted`` are the
ones the VM can wrap; the rest of the registry runs whole programs only.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from esolangs.exceptions import UnknownLanguageError
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import RUNNERS

if TYPE_CHECKING:
    # Only for the chooser stand-in's signature; the interpreters are
    # imported lazily inside the VMs that use them.
    from esolangs.interpreters.grid_based.cod import _Direction


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


class _BaseVM:
    """Shared ``output`` capture and the run-state accessor plumbing.

    Subclasses supply ``step``, ``halted``, and the language-shaped
    ``ip``/``memory``/``stack``; ``output`` is captured here.
    """

    def __init__(self, program: str | list[str], stdin: str = "") -> None:
        """Create a VM for ``program`` reading input from ``stdin``."""
        self._io = ScriptedIO(stdin)
        self._program = program

    @property
    def output(self) -> str:
        return self._io.getvalue()

    def step(self) -> None:
        raise NotImplementedError

    @property
    def halted(self) -> bool:
        raise NotImplementedError

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        raise NotImplementedError

    @property
    def memory(self) -> list[int]:
        raise NotImplementedError

    @property
    def stack(self) -> list[object]:
        raise NotImplementedError


class _DelegatingVM(_BaseVM):
    """A VM for an interpreter that describes its own shape.

    The older adapters below spell ``ip``/``memory``/``stack`` here, in
    ``vm.py``, as expressions reaching into a ``_Machine``'s attributes.
    That put the language-shaped mapping -- which is genuinely different for
    all 61 of them -- in a file that does not otherwise know the languages.
    An interpreter whose ``_Machine`` exposes those three properties itself
    keeps the mapping next to the state it describes, and its adapter
    shrinks to the one thing that really is per-language: how the machine is
    constructed.

    Subclasses provide ``__init__`` only.  Everything else forwards.

    ``memory`` and ``stack`` are copied on the way out.  The machine may
    hand back its live store -- several expose the list itself, under
    exactly these names -- and a caller holding ``vm.memory`` must not be
    able to write into a running machine through it.  Copying here rather
    than in each interpreter keeps that guarantee in one place, and turns
    the widening from ``Sequence`` into the ``list`` :class:`VM` promises.
    """

    _machine: _StepMachineWithShape

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


class _SbleqVM(_DelegatingVM):
    """OISC cells + instruction pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.sbleq import _Machine

        self._machine = _Machine(io=self._io, mem=[int(tok) for tok in program.split()])


class _GraphemeVM(_DelegatingVM):
    """Stack + variables; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.grapheme import _Machine

        self._machine = _Machine.of(program, self._io)


class _QoiblVM(_DelegatingVM):
    """256-entry variable list; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.qoibl import State

        self._machine = State.of(program, self._io)


class _EvalVM(_DelegatingVM):
    """Two stacks + active index; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.eval import State

        self._machine = State(io=self._io, sym=program)


class _ModulousVM(_DelegatingVM):
    """Stack + variables; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.modulous import State

        self._machine = State.of(program, self._io)


class _LaserFuckVM(_DelegatingVM):
    """2D grid; the interpreter describes its own shape.

    The heading is fixed to 0 (up) so stepping is reproducible; the
    interpreter's own ``run`` draws a random heading when none is given.
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.laserfuck import _Machine

        self._machine = _Machine(program.splitlines(), self._io, heading=0)


class _FirstChoiceRNG:
    """A deterministic stand-in for COD's random-junction chooser.

    Always takes the first (lexicographically, since ``_open_dirs`` iterates
    ``N``/``S``/``E``/``W`` in that fixed order) option, so VM stepping is
    reproducible instead of drawing from ``secrets`` on every genuine
    junction.
    """

    def choice(self, options: list[_Direction]) -> _Direction:
        return options[0]


class _CODVM(_DelegatingVM):
    """2D grid with possibly many live cods; the interpreter describes its shape.

    Random junctions (not exercised by the boolean generator's branch-free
    programs) are resolved deterministically via :class:`_FirstChoiceRNG` so
    stepping is reproducible.  That is this adapter's business rather than
    the language's, which is why the constructor stays spelled out here.
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.cod import _Machine

        self._machine = _Machine(program, self._io, rng=_FirstChoiceRNG())


class _PointBreakVM(_DelegatingVM):
    """Variable store + loop frames; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.point_break import _Machine

        self._machine = _Machine(program, self._io)


class _ArrowQueueVM(_DelegatingVM):
    """Direction queue; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.arrowqueue import _Machine

        self._machine = _Machine(program.splitlines())


class _APainterAntVM(_DelegatingVM):
    """2D grid; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine

        self._machine = _Machine(program)


class _SuffolkVM(_DelegatingVM):
    """Tape + accumulator; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.suffolk import _Machine

        self._machine = _Machine(program, self._io)


# Language name -> VM adapter.  Only interpreters with a step()/halted state
# object are wrappable; the rest raise UnknownLanguageError.
# Most adapters are derived from the registry: once an interpreter
# describes its own shape, the only per-language facts left are the two
# ``RUNNERS`` already holds.  The rest are spelled out because they need
# extra setup, override ``step()``, or build their machine differently
# from the way their runner does.
_VM_ADAPTERS: dict[str, type[_BaseVM]] = {
    "S*bleq": _SbleqVM,
    "Grapheme": _GraphemeVM,
    "Qoibl": _QoiblVM,
    "Eval": _EvalVM,
    "Modulous": _ModulousVM,
    "LaserFuck": _LaserFuckVM,
    "COD": _CODVM,
    "Point Break": _PointBreakVM,
    "ArrowQueue": _ArrowQueueVM,
    "A Painter Ant": _APainterAntVM,
    "Suffolk": _SuffolkVM,
}


# Languages whose adapter is pure boilerplate over the registry entry.
_DERIVED_LANGUAGES = (
    "Bitdeque",
    "3D Brainfuck",
    "%^2^-1",
    "123",
    "3x",
    "6-5",
    "AddSubJump",
    "BF-PDA",
    "BFStack",
    "BIO",
    "Back",
    "Basicfuck",
    "Between",
    "BrainIf",
    "CV(N)(C)",
    "Circlefuck",
    "Circuit Diagram",
    "Clockwise",
    "Collatz Multiverse",
    "Container",
    "Decleq",
    "Dig",
    "Dimensional",
    "Factor",
    "Fargo",
    "Flowchart",
    "Forbin",
    "Forþ",
    "Home Row",
    "Jaune",
    "Lamfunc",
    "Minifuck",
    "Minsky Swap",
    "MyScript",
    "Nevermind",
    "NoComment",
    "Painfuck",
    "Polynomial",
    "RAM0",
    "ROTfuck",
    "SLOW ACV MAMMALIAN",
    "Sophie",
    "Streetcode",
    "Suptiftam",
    "Taglate",
    "Unsquare",
    "WII2D",
    "ZTOALC L",
    "bit~",
    "brainfuck",
)


def _derived_adapter(language: str) -> type[_DelegatingVM]:
    """Build the adapter for a language whose wrapper is pure boilerplate.

    Once an interpreter describes its own shape, most adapters differ only
    in which module to import and whether the program is passed as text or
    as lines -- and ``RUNNERS`` already records both, because ``run`` needs
    exactly the same two facts.  Deriving from it means the adapter set
    cannot drift from the runner set, and adding a language that follows
    the common shape needs no code here at all.

    The languages this does *not* cover keep an explicit class below: the
    ones whose machine needs extra setup, whose adapter overrides
    ``step()``, or whose construction disagrees with their runner's (Point
    Break's runner splits its program where the machine does not; Suffolk's
    passes a ``limit`` the VM leaves at its default).
    """
    module_path, split, _ = RUNNERS[language]

    class _Derived(_DelegatingVM):
        def __init__(self, program: str, stdin: str = "") -> None:
            super().__init__(program, stdin)
            import importlib

            module = importlib.import_module(f"esolangs.interpreters.{module_path}")
            code = program.splitlines() if split else program
            # ``_Machine`` is private to its module but is the state object
            # this whole file is built around; the explicit adapters below
            # import it by name for the same reason.
            machine = getattr(module, "_Machine")  # noqa: B009
            self._machine = machine(code, self._io)

    _Derived.__name__ = _Derived.__qualname__ = f"_{language}VM"
    _Derived.__doc__ = f"Adapter for {language}; the interpreter describes its shape."
    return _Derived


_VM_ADAPTERS.update({name: _derived_adapter(name) for name in _DERIVED_LANGUAGES})


def make_vm(language: str, program: str, stdin: str = "") -> VM:
    """Return a step-and-inspect wrapper around ``language``'s interpreter.

    The wrapper exposes ``step()``, ``halted``, ``output``, ``ip``,
    ``memory``, and ``stack`` between commands.  ``stdin`` is fed to the
    program line by line, like :func:`esolangs.run`.  A language whose
    interpreter does not expose a step-capable state object raises
    :class:`UnknownLanguageError`.
    """
    if language not in RUNNERS:
        raise UnknownLanguageError(language)
    try:
        adapter = _VM_ADAPTERS[language]
    except KeyError:
        raise UnknownLanguageError(language) from None
    return adapter(program, stdin)
