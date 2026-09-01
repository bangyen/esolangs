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

    The three properties are the ones :class:`VM` exposes; an interpreter
    that defines them can be wrapped by :class:`_DelegatingVM` without any
    per-language code in this module.  ``stack`` is ``list[object]`` to match
    :class:`VM` exactly -- ``list`` is invariant, so an interpreter declaring
    ``list[int]`` would not satisfy this.
    """

    @property
    def ip(self) -> int | tuple[int, ...] | None:
        """The current code/instruction position."""

    @property
    def memory(self) -> list[int]:
        """The addressable cells, or ``[]`` where there is no such store."""

    @property
    def stack(self) -> list[object]:
        """The stack, or ``[]`` where the language has none."""


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
        return self._machine.memory

    @property
    def stack(self) -> list[object]:
        return self._machine.stack


class _BrainfuckVM(_DelegatingVM):
    """Tape + pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.brainfuck import _Machine

        self._machine = _Machine(program, self._io)


class _SbleqVM(_DelegatingVM):
    """OISC cells + instruction pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.sbleq import _Machine

        self._machine = _Machine(io=self._io, mem=[int(tok) for tok in program.split()])


class _DimensionalVM(_DelegatingVM):
    """Pointer hierarchy; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.dimensional import _Machine

        self._machine = _Machine(program, self._io)


class _GraphemeVM(_BaseVM):
    """Stack + variables; ``ip`` is the call stack's cursors, root-to-leaf.

    Each active call frame (``G``/``I``/``Q``/``Z`` push one) contributes its
    ``pc`` to the tuple, so ``ip`` grows and shrinks with recursion depth
    instead of folding every frame into the active one's position.  A
    breakpoint on a specific ``ip`` is therefore depth-sensitive: ``(5,)``
    matches only a single top-level frame at pc 5, not pc 5 one call deeper
    (``(2, 5)``).
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.grapheme import _Frame, _Machine

        if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in program):
            raise ValueError(
                "Grapheme programs may only contain uppercase Latin letters"
            )
        self._machine = _Machine(self._io, 1_000_000)
        self._machine.frames.append(_Frame(program, 0))

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        # a frame is only ever popped once its own pc reaches len(code), so
        # frames == [] implies the top-level frame finished at len(program).
        frames = self._machine.frames
        return tuple(f.pc for f in frames) if frames else (len(self._program),)

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)


class _QoiblVM(_BaseVM):
    """256-entry variable list; ``ip`` is the expression cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.qoibl import State, tokenize

        self._state = State(io=self._io)
        self._state.code = tokenize(program)

    @property
    def halted(self) -> bool:
        return self._state.halted

    def step(self) -> None:
        self._state.step()

    @property
    def ip(self) -> int:
        return self._state.ind

    @property
    def memory(self) -> list[int]:
        return [self._state.var.get(k, 0) for k in range(256)]

    @property
    def stack(self) -> list[object]:
        return []


class _EvalVM(_BaseVM):
    """Two stacks + active index; ``ip`` is the code cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.eval import State

        self._state = State(io=self._io, sym=program)

    @property
    def halted(self) -> bool:
        return self._state.halted

    def step(self) -> None:
        self._state.step()

    @property
    def ip(self) -> int:
        return self._state.ind

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._state.stk[self._state.ptr])


class _ModulousVM(_BaseVM):
    """Stack + variables; ``ip`` is the token cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        import re

        from esolangs.interpreters.stack_based.modulous import State

        self._state = State(var={f"VAR{k}": 0 for k in range(1, 5)}, io=self._io)
        self._state.tokens = [
            k[0] for k in re.compile(r'\[([^\[\]\"]*("[^"]*")?)]').findall(program)
        ]

    @property
    def halted(self) -> bool:
        return self._state.halted

    def step(self) -> None:
        self._state.step()

    @property
    def ip(self) -> int:
        return self._state.ind

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._state.stk)


class _ForthVM(_BaseVM):
    """Stack + scope table; ``ip`` is the call stack's cursors, root-to-leaf.

    Each active scope (``;``/``(``/``[`` pushes one) contributes its ``pc``
    to the tuple, so ``ip`` grows and shrinks with call depth instead of
    folding every frame into the active one's position.  A breakpoint on a
    specific ``ip`` is therefore depth-sensitive: ``(5,)`` matches only a
    single top-level frame at pc 5, not pc 5 one call deeper (``(2, 5)``).
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.forth import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        # a frame is only ever popped once its own pc reaches len(code), so
        # frames == [] implies the top-level frame finished at len(program).
        frames = self._machine.frames
        return tuple(f.pc for f in frames) if frames else (len(self._program),)

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)


class _LaserFuckVM(_BaseVM):
    """2D grid; ``ip`` is the active laser's (row, col, heading).

    The heading is fixed to 0 (up) so stepping is reproducible; the
    interpreter's own ``run`` draws a random heading when none is given.
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.laserfuck import _Machine

        self._machine = _Machine(program.splitlines(), self._io, heading=0)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        machine = self._machine
        if machine.halted:
            return
        machine.step()
        if not machine.lsrs:
            machine.dump()

    @property
    def ip(self) -> tuple[int, ...]:
        return self._machine.pos

    @property
    def memory(self) -> list[int]:
        return [v for v, _ in self._machine.tape]

    @property
    def stack(self) -> list[object]:
        return []


class _FirstChoiceRNG:
    """A deterministic stand-in for COD's random-junction chooser.

    Always takes the first (lexicographically, since ``_open_dirs`` iterates
    ``N``/``S``/``E``/``W`` in that fixed order) option, so VM stepping is
    reproducible instead of drawing from ``secrets`` on every genuine
    junction.
    """

    def choice(self, options: list[_Direction]) -> _Direction:
        return options[0]


_COD_HEADINGS = {"N": 0, "S": 1, "E": 2, "W": 3}


class _CODVM(_BaseVM):
    """2D grid with possibly many live cods.

    ``ip`` is every cod's ``(row, col, heading, value)`` flattened into one
    tuple (heading coded ``N=0``/``S=1``/``E=2``/``W=3``), sorted for a
    stable order.  Random junctions (not exercised by the boolean
    generator's branch-free programs) are resolved deterministically via
    :class:`_FirstChoiceRNG` so stepping is reproducible.
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.cod import _Machine

        self._machine = _Machine(program, self._io, rng=_FirstChoiceRNG())

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        cods = sorted(
            (cod.r, cod.c, _COD_HEADINGS[cod.d], cod.value)
            for cod in self._machine.cods
        )
        return tuple(v for cod in cods for v in cod)

    @property
    def memory(self) -> list[int]:
        return [cod.value for cod in self._machine.cods]

    @property
    def stack(self) -> list[object]:
        return []


class _PointBreakVM(_DelegatingVM):
    """Variable store + loop frames; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.point_break import _Machine

        self._machine = _Machine(program, self._io)


class _AddSubJumpVM(_BaseVM):
    """Self-modifying memory + instruction pointer; ``memory`` is the cells."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.addsubjump import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ip

    @property
    def memory(self) -> list[int]:
        return list(self._machine.memory)

    @property
    def stack(self) -> list[object]:
        return []


class _ArrowQueueVM(_DelegatingVM):
    """Direction queue; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.arrowqueue import _Machine

        self._machine = _Machine(program.splitlines())


class _BitdequeVM(_BaseVM):
    """Token cursor + deque; ``ip`` cursor, ``memory`` deque, ``stack`` register."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.queue_based.bitdeque import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        machine = self._machine
        if machine.halted:
            return
        machine.step()
        if machine.ind >= len(machine.tokens):
            machine.render()  # the deque is printed once the program ends

    @property
    def ip(self) -> int:
        return self._machine.ind

    @property
    def memory(self) -> list[int]:
        return list(self._machine.deq)

    @property
    def stack(self) -> list[object]:
        return [self._machine.reg]


class _APainterAntVM(_DelegatingVM):
    """2D grid; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine

        self._machine = _Machine(program)


class _ClockwiseVM(_DelegatingVM):
    """2D ring; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.clockwise import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _DigVM(_DelegatingVM):
    """2D mole grid; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.dig import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _Wii2dVM(_DelegatingVM):
    """2D wrap-around grid; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.wii2d import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _DecleqVM(_BaseVM):
    """Self-modifying memory + pointer; ``memory`` the cells."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.decleq import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.pc

    @property
    def memory(self) -> list[int]:
        return list(self._machine.memory)

    @property
    def stack(self) -> list[object]:
        return []


class _SixFiveVM(_DelegatingVM):
    """Token tape + cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.six_five import _Machine

        self._machine = _Machine(program, self._io)


class _BackVM(_DelegatingVM):
    """2D beam; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.back import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _BIOVM(_DelegatingVM):
    """Registers + loop stack + cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.bio import _Machine

        self._machine = _Machine(program, self._io)


class _NoCommentVM(_BaseVM):
    """Byte tape + stack + cursor; ``ip`` the cursor, ``memory`` the tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.nocomment import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ind

    @property
    def memory(self) -> list[int]:
        return list(self._machine.tape)

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)


class _ThreeDBrainfuckVM(_BaseVM):
    """2D block grid; ``ip`` is the pointer's position + heading, ``memory`` cells."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        return (
            *self._machine.ip,
            *self._machine.heading,
        )

    @property
    def memory(self) -> list[int]:
        return [v for _, v in sorted(self._machine.cells.items())]

    @property
    def stack(self) -> list[object]:
        return []


class _FactorVM(_DelegatingVM):
    """Decoded brainfuck machine; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.factor import _Machine

        self._machine = _Machine(program, self._io)


class _BasicfuckVM(_DelegatingVM):
    """Compiled code + frame stack; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.basicfuck import _Machine

        self._machine = _Machine(program, self._io)


class _PainfuckVM(_DelegatingVM):
    """Translated tape + cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.painfuck import _Machine

        self._machine = _Machine(program, self._io)


class _BitTildeVM(_DelegatingVM):
    """Bit pool + pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

        self._machine = _Machine(program, self._io)


class _CollatzMultiverseVM(_DelegatingVM):
    """Named registers + line pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.collatz_multiverse import _Machine

        self._machine = _Machine(program, self._io)


class _PolynomialVM(_DelegatingVM):
    """Single register + cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.polynomial import _Machine

        self._machine = _Machine(program, self._io)


class _RAM0VM(_BaseVM):
    """Two registers + RAM; ``ip`` the token cursor, ``memory`` z, n, then RAM."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.ram0 import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ind

    @property
    def memory(self) -> list[int]:
        ram = self._machine.ram
        return [self._machine.z, self._machine.n, *(ram[k] for k in sorted(ram))]

    @property
    def stack(self) -> list[object]:
        return []


class _MinskySwapVM(_DelegatingVM):
    """Two registers + pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.minsky_swap import _Machine

        self._machine = _Machine(program, self._io)


class _HomeRowVM(_DelegatingVM):
    """5x5 torus grid + pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.home_row import _Machine

        self._machine = _Machine(program, self._io)


class _UnsquareVM(_BaseVM):
    """Stack + accumulator; ``ip`` the cursor, ``memory`` the accumulator."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.unsquare import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ind

    @property
    def memory(self) -> list[int]:
        return [self._machine.acc]

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)


class _ROTFuckVM(_DelegatingVM):
    """Rotating tape + cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.rotfuck import _Machine

        self._machine = _Machine(program, self._io)


class _CirclefuckVM(_DelegatingVM):
    """Self-modifying circular tape; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        self._machine = _Machine(program, self._io)


class _BFStackVM(_DelegatingVM):
    """Data stack + loop stack + cursor; the interpreter describes its shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.bfstack import _Machine

        self._machine = _Machine(program, self._io)


class _BrainIfVM(_DelegatingVM):
    """Cell tape + line cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.brainif import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _MinifuckVM(_DelegatingVM):
    """Binary tape + cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.minifuck import _Machine

        self._machine = _Machine(program, self._io)


class _TaglateVM(_DelegatingVM):
    """Queue + token cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.queue_based.taglate import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _OneTwoThreeVM(_DelegatingVM):
    """Unbounded bit tape + pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.one_two_three import _Machine

        self._machine = _Machine(program, self._io)


class _PctSquaredMinusOneVM(_DelegatingVM):
    """Accumulator + cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.pct_squared_minus_one import (
            _Machine,
        )

        self._machine = _Machine(program, self._io)


class _SuffolkVM(_DelegatingVM):
    """Tape + accumulator; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.suffolk import _Machine

        self._machine = _Machine(program, self._io)


class _ContainerVM(_DelegatingVM):
    """Named containers + tick count; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.container import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _NevermindVM(_DelegatingVM):
    """Named variables + line cursor; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.nevermind import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _BFPDAVM(_BaseVM):
    """Bit stack + cursor; ``ip`` the cursor, ``stack`` the bits."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.bf_pda import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ip

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)


class _ThreeXVM(_BaseVM):
    """Rational stack + cursor; ``ip`` the cursor, ``stack`` the rationals."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.three_x import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ind

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stack)


class _SophieVM(_DelegatingVM):
    """Accumulator + loop stack; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.sophie import _Machine

        self._machine = _Machine(program, self._io)


class _JauneVM(_DelegatingVM):
    """Cell tape + hold register; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.jaune import _Machine

        self._machine = _Machine(program, self._io)


class _SlowAcvMammalianVM(_DelegatingVM):
    """23 arrays + pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

        self._machine = _Machine(program, self._io)


class _ZtoalcLVM(_DelegatingVM):
    """Collatz-trajectory pointer; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.ztoalc_l import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _BetweenVM(_DelegatingVM):
    """Goto-based variables; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.between import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


class _MyScriptVM(_BaseVM):
    """Frame stack + scopes; ``ip`` is (frame depth, position in top frame)."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.myscript import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, int] | None:
        if not self._machine.stack:
            return None
        top = self._machine.stack[-1]
        return len(self._machine.stack), top.pos

    @property
    def memory(self) -> list[int]:
        if not self._machine.stack:
            return []
        scope = self._machine.stack[-1].scope
        return [v for v in scope.vars.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        return []


class _LamfuncVM(_DelegatingVM):
    """Prefix-call evaluator; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.lamfunc import _Machine

        self._machine = _Machine(program, self._io)


class _CvncVM(_DelegatingVM):
    """Accumulator and deque; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.cvnc import _Machine

        self._machine = _Machine(program, self._io)


class _FargoVM(_DelegatingVM):
    """Prefix-call evaluator; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.fargo import _Machine

        self._machine = _Machine(program, self._io)


class _ForbinVM(_BaseVM):
    """Call stack; ``ip`` is each frame's statement cursor, root-to-leaf."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.forbin import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        frames = self._machine.frames
        return tuple(f.pos for f in frames) if frames else (len(self._program),)

    @property
    def memory(self) -> list[int]:
        if not self._machine.frames:
            return []
        return [v for v in self._machine.frames[-1].locals.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        return []


class _SuptiftamVM(_BaseVM):
    """Global scope + tapes; ``ip`` is the top-level statement cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.suptiftam import _Machine, _Var

        self._machine = _Machine(program, self._io)
        self._Var = _Var

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ind

    @property
    def memory(self) -> list[int]:
        return [
            v.value
            for v in self._machine.state.globals.values()
            if isinstance(v, self._Var) and v.kind == "int"
        ]

    @property
    def stack(self) -> list[object]:
        return []


class _StreetcodeVM(_BaseVM):
    """2D street grid; ``ip`` is the car's (row, col, heading), ``memory`` the cells.

    The heading is spelled ``"N"``/``"E"``/``"S"``/``"W"`` on the machine and
    reported here as its index into that order, so ``ip`` stays all-integer
    like every other 2D language's.  The tape is a sparse dict keyed by CP,
    which never goes negative -- ``LEFT`` at zero halts -- so ``memory`` is
    the dense prefix up to the highest cell touched.
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.streetcode import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        machine = self._machine
        return (machine.row, machine.col, "NESW".index(machine.heading))

    @property
    def memory(self) -> list[int]:
        cells = self._machine.cells
        if not cells:
            return []
        return [cells.get(i, 0) for i in range(max(cells) + 1)]

    @property
    def stack(self) -> list[object]:
        return []


class _FlowchartVM(_BaseVM):
    """Forking 2D pointers; ``ip`` is the first live one, ``memory`` the deques.

    A Flowchart program runs several pointers at once, so there is no single
    cursor to report: ``ip`` is the first pointer still running, as
    ``(row, col, drow, dcol)`` with the heading flattened, and ``None`` once
    every pointer has stopped on an ``(( ))``.  ``memory`` is the shared tape
    of deques concatenated in index order, which is what the pointers read
    and write between them.
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.flowchart import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...] | None:
        for pointer in self._machine.pointers:
            if not pointer.done:
                return (pointer.row, pointer.col, *pointer.d)
        return None

    @property
    def memory(self) -> list[int]:
        deques = self._machine.deques
        return [v for key in sorted(deques) for v in deques[key]]

    @property
    def stack(self) -> list[object]:
        return []


class _CircuitDiagramVM(_DelegatingVM):
    """Generation-based circuit; the interpreter describes its own shape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.circuit_diagram import _Machine

        self._machine = _Machine(program.splitlines(), self._io)


# Language name -> VM adapter.  Only interpreters with a step()/halted state
# object are wrappable; the rest raise UnknownLanguageError.
_VM_ADAPTERS: dict[str, type[_BaseVM]] = {
    "brainfuck": _BrainfuckVM,
    "S*bleq": _SbleqVM,
    "Dimensional": _DimensionalVM,
    "Grapheme": _GraphemeVM,
    "Qoibl": _QoiblVM,
    "Eval": _EvalVM,
    "Modulous": _ModulousVM,
    "LaserFuck": _LaserFuckVM,
    "COD": _CODVM,
    "Point Break": _PointBreakVM,
    "ArrowQueue": _ArrowQueueVM,
    "A Painter Ant": _APainterAntVM,
    "Clockwise": _ClockwiseVM,
    "Dig": _DigVM,
    "WII2D": _Wii2dVM,
    "123": _OneTwoThreeVM,
    "Forþ": _ForthVM,
    "AddSubJump": _AddSubJumpVM,
    "Bitdeque": _BitdequeVM,
    "BrainIf": _BrainIfVM,
    "Minifuck": _MinifuckVM,
    "Taglate": _TaglateVM,
    "ROTfuck": _ROTFuckVM,
    "Circlefuck": _CirclefuckVM,
    "BFStack": _BFStackVM,
    "Decleq": _DecleqVM,
    "6-5": _SixFiveVM,
    "Back": _BackVM,
    "BIO": _BIOVM,
    "NoComment": _NoCommentVM,
    "3D Brainfuck": _ThreeDBrainfuckVM,
    "Factor": _FactorVM,
    "Basicfuck": _BasicfuckVM,
    "Painfuck": _PainfuckVM,
    "bit~": _BitTildeVM,
    "Collatz Multiverse": _CollatzMultiverseVM,
    "Polynomial": _PolynomialVM,
    "RAM0": _RAM0VM,
    "Minsky Swap": _MinskySwapVM,
    "Home Row": _HomeRowVM,
    "Unsquare": _UnsquareVM,
    "%^2^-1": _PctSquaredMinusOneVM,
    "Suffolk": _SuffolkVM,
    "Container": _ContainerVM,
    "Nevermind": _NevermindVM,
    "BF-PDA": _BFPDAVM,
    "3x": _ThreeXVM,
    "Sophie": _SophieVM,
    "Jaune": _JauneVM,
    "SLOW ACV MAMMALIAN": _SlowAcvMammalianVM,
    "ZTOALC L": _ZtoalcLVM,
    "Between": _BetweenVM,
    "MyScript": _MyScriptVM,
    "Lamfunc": _LamfuncVM,
    "CV(N)(C)": _CvncVM,
    "Fargo": _FargoVM,
    "Forbin": _ForbinVM,
    "Suptiftam": _SuptiftamVM,
    "Streetcode": _StreetcodeVM,
    "Flowchart": _FlowchartVM,
    "Circuit Diagram": _CircuitDiagramVM,
}


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
