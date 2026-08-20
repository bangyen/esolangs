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

from collections.abc import Hashable
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


class _BrainfuckVM(_BaseVM):
    """Tape + pointer; ``ip`` is the code cursor, ``memory`` the tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.brainfuck import _Machine

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
        return []


class _SbleqVM(_BaseVM):
    """OISC cells + instruction pointer; ``memory`` is the program memory."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.sbleq import _Machine

        self._machine = _Machine(io=self._io, mem=[int(tok) for tok in program.split()])

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
        return list(self._machine.mem)

    @property
    def stack(self) -> list[object]:
        return []


class _DimensionalVM(_BaseVM):
    """Pointer hierarchy; ``ip`` is the code cursor, ``memory`` the axes."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.dimensional import _Runner

        self._runner = _Runner(program, self._io)

    @property
    def halted(self) -> bool:
        return self._runner.halted

    def step(self) -> None:
        self._runner.step()

    @property
    def ip(self) -> int:
        return self._runner.ind

    @property
    def memory(self) -> list[int]:
        # the single byte the pointer hierarchy currently addresses
        return [self._runner.machine.value()]

    @property
    def stack(self) -> list[object]:
        return []


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
        from esolangs.interpreters.register_based.qoibl import State

        self._state = State(io=self._io)
        self._state.code = program.splitlines()

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
    """2D grid; ``ip`` is the active laser's (x, y, heading).

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


class _PointBreakVM(_BaseVM):
    """Variable store + loop frames; ``ip`` is the statement cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.point_break import _Machine

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
        return [self._machine.variables[k] for k in sorted(self._machine.variables)]

    @property
    def stack(self) -> list[object]:
        return []


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


class _ArrowQueueVM(_BaseVM):
    """Direction queue; ``ip`` is the IP's (x, y, heading)."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.arrowqueue import _Machine

        self._machine = _Machine(program.splitlines())

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        return (self._machine.x, self._machine.y, self._machine.d)

    @property
    def memory(self) -> list[int]:
        return []

    @property
    def stack(self) -> list[object]:
        return list(self._machine.queue)


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


class _APainterAntVM(_BaseVM):
    """2D grid; ``ip`` is the instruction cursor, ``memory`` the cell colours.

    The program never halts (implicit loop), so the debugger's ``halted``
    stays ``False`` and the state-cycle hang detector is the only way to
    prove a program loops.
    """

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine

        self._machine = _Machine(program)

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
        return [v for _, v in sorted(self._machine.grid.items())]

    @property
    def stack(self) -> list[object]:
        return []


class _TwoDFishVM(_BaseVM):
    """2D grid; ``ip`` is the (x, y, direction), ``memory`` the accumulator."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.two_d_fish import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        return (self._machine.x, self._machine.y, "/\\v^".find(self._machine.d or ""))

    @property
    def memory(self) -> list[int]:
        return [self._machine.acc]

    @property
    def stack(self) -> list[object]:
        return []


class _ClockwiseVM(_BaseVM):
    """2D ring; ``ip`` is the pointer's (x, y, heading), ``memory`` the accumulator."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.clockwise import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        return (self._machine.x, self._machine.y, self._machine.r)

    @property
    def memory(self) -> list[int]:
        return [self._machine.acc]

    @property
    def stack(self) -> list[object]:
        return []


class _DigVM(_BaseVM):
    """2D mole grid; ``ip`` is the mole's (x, y, heading), ``memory`` the mole."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.dig import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        return (self._machine.x, self._machine.y, self._machine.move)

    @property
    def memory(self) -> list[int]:
        return [self._machine.mole]

    @property
    def stack(self) -> list[object]:
        return []


class _Wii2dVM(_BaseVM):
    """2D wrap-around grid; ``ip`` is (x, y, heading), ``memory`` the accumulator."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.grid_based.wii2d import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        return (self._machine.x, self._machine.y, self._machine.vel)

    @property
    def memory(self) -> list[int]:
        return [self._machine.acc]

    @property
    def stack(self) -> list[object]:
        return []


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


class _SixFiveVM(_BaseVM):
    """Token tape + cursor; ``ip`` the cursor, ``memory`` the cell tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.six_five import _Machine

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
        return []


class _BackVM(_BaseVM):
    """2D beam; ``ip`` is the beam's (x, y, direction), ``memory`` the bit tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.back import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        return (self._machine.x, self._machine.y, self._machine.a, self._machine.b)

    @property
    def memory(self) -> list[int]:
        return list(self._machine.tape)

    @property
    def stack(self) -> list[object]:
        return []


class _BIOVM(_BaseVM):
    """Registers + loop stack + cursor; ``ip`` the cursor, ``memory`` the regs."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.bio import _Machine

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
        return list(self._machine.reg)

    @property
    def stack(self) -> list[object]:
        return list(self._machine.stk)


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


class _FactorVM(_BaseVM):
    """Decoded brainfuck machine; ``ip`` the cursor, ``memory`` the tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.factor import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.bf.ind

    @property
    def memory(self) -> list[int]:
        return list(self._machine.bf.tape)

    @property
    def stack(self) -> list[object]:
        return []


class _BasicfuckVM(_BaseVM):
    """Compiled code + frame stack; ``ip`` the top frame's cursor, ``memory`` tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.basicfuck import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int | None:
        return self._machine.frames[-1].ptr if self._machine.frames else None

    @property
    def memory(self) -> list[int]:
        return list(self._machine.tape.cells())

    @property
    def stack(self) -> list[object]:
        return []


class _PainfuckVM(_BaseVM):
    """Translated tape + cursor; ``ip`` the cursor, ``memory`` the tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.painfuck import _Machine

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
        return list(self._machine.loop)


class _BitTildeVM(_BaseVM):
    """Bit pool + pointer; ``ip`` the cursor, ``memory`` the pool."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.bit_tilde import _Machine

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
        return []


class _CollatzMultiverseVM(_BaseVM):
    """Named registers + line pointer; ``ip`` the line, ``memory`` the regs."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.collatz_multiverse import _Machine

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
        return [self._machine.registers[k] for k in sorted(self._machine.registers)]

    @property
    def stack(self) -> list[object]:
        return []


class _PolynomialVM(_BaseVM):
    """Single register + cursor; ``ip`` the cursor, ``memory`` the register."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.polynomial import _Machine

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
        return [self._machine.reg]

    @property
    def stack(self) -> list[object]:
        return []


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


class _MinskySwapVM(_BaseVM):
    """Two registers + pointer; ``ip`` the cursor, ``memory`` both registers."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.minsky_swap import _Machine

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
        return list(self._machine.reg)

    @property
    def stack(self) -> list[object]:
        return []


class _HomeRowVM(_BaseVM):
    """5x5 torus grid + pointer; ``ip`` the cursor, ``memory`` the 25 cells."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.home_row import _Machine

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
        return list(self._machine.grid)

    @property
    def stack(self) -> list[object]:
        return []


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


class _ROTFuckVM(_BaseVM):
    """Rotating tape + cursor; ``ip`` the cursor, ``memory`` the tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.rotfuck import _Machine

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
        return []


class _CirclefuckVM(_BaseVM):
    """Self-modifying circular tape + cursor; ``ip`` cursor, ``memory`` cells."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.circlefuck import _Machine

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
        return list(self._machine.cells)

    @property
    def stack(self) -> list[object]:
        return []


class _BFStackVM(_BaseVM):
    """Data stack + loop stack + cursor; ``ip`` the cursor, ``stack`` the data."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.stack_based.bfstack import _Machine

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
        return list(self._machine.stk)


class _BrainIfVM(_BaseVM):
    """Cell tape + line cursor; ``ip`` the cursor, ``memory`` the cells."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.brainif import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

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
        return list(self._machine.cells)

    @property
    def stack(self) -> list[object]:
        return []


class _MinifuckVM(_BaseVM):
    """Binary tape + cursor; ``ip`` the cursor, ``memory`` the tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.minifuck import _Machine

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
        return []


class _TaglateVM(_BaseVM):
    """Queue + token cursor; ``ip`` the cursor, ``memory`` the queue."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.queue_based.taglate import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

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
        return list(self._machine.queue)

    @property
    def stack(self) -> list[object]:
        return []


class _OneTwoThreeVM(_BaseVM):
    """Single data byte + pointer mask; ``ip`` is the code cursor."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.one_two_three import _Machine

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
        return [self._machine.data & 0xFF]

    @property
    def stack(self) -> list[object]:
        return []


class _PctSquaredMinusOneVM(_BaseVM):
    """Accumulator + cursor; ``ip`` the cursor, ``memory`` the accumulator."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.pct_squared_minus_one import (
            _Machine,
        )

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
        return []


class _SuffolkVM(_BaseVM):
    """Tape + accumulator; ``ip`` the cursor, ``memory`` the tape."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.suffolk import _Machine

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
        return []


class _ContainerVM(_BaseVM):
    """Named containers + tick count; ``ip`` the tick, ``memory`` the values."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.container import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.tick

    @property
    def memory(self) -> list[int]:
        return [self._machine.var[k] for k in sorted(self._machine.var)]

    @property
    def stack(self) -> list[object]:
        return []


class _NevermindVM(_BaseVM):
    """Named variables + line cursor; ``ip`` the line, ``memory`` the vars."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.nevermind import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

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
            int(v)
            for v in (self._machine.var[k] for k in sorted(self._machine.var))
            if isinstance(v, (int, float))
        ]

    @property
    def stack(self) -> list[object]:
        return []


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


class _ABCDirectionVM(_BaseVM):
    """Bit tape + donut grid pointer; ``ip`` is (x, y, direction)."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.abcdirection import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> tuple[int, ...]:
        return (self._machine.x, self._machine.y, self._machine.d)

    @property
    def memory(self) -> list[int]:
        return [self._machine.tape.get(k, 0) for k in sorted(self._machine.tape)]

    @property
    def stack(self) -> list[object]:
        return list(self._machine.queue)


class _SophieVM(_BaseVM):
    """Accumulator + loop stack; ``ip`` the cursor, ``memory`` the acc."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.sophie import _Machine

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
        return list(self._machine.stk)


class _JauneVM(_BaseVM):
    """Cell tape + hold register; ``ip`` the command position."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.jaune import _Machine

        self._machine = _Machine(program, self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.pos

    @property
    def memory(self) -> list[int]:
        return list(self._machine.cells)

    @property
    def stack(self) -> list[object]:
        return list(self._machine.call_stack)


class _SlowAcvMammalianVM(_BaseVM):
    """23 arrays + pointer; ``memory`` is the current array, ``stack`` all 23."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine

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
        return list(self._machine.lst[self._machine.ptr])

    @property
    def stack(self) -> list[object]:
        return [row for arr in self._machine.lst for row in arr]


class _ZtoalcLVM(_BaseVM):
    """Collatz-trajectory pointer; ``memory`` is the sorted variable values."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.other.ztoalc_l import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

    @property
    def halted(self) -> bool:
        return self._machine.halted

    def step(self) -> None:
        self._machine.step()

    @property
    def ip(self) -> int:
        return self._machine.ptr

    @property
    def memory(self) -> list[int]:
        return [v for _, v in sorted(self._machine.var.items()) if isinstance(v, int)]

    @property
    def stack(self) -> list[object]:
        return []


class _BetweenVM(_BaseVM):
    """Goto-based variables; ``ip`` the program counter, ``memory`` the ints."""

    def __init__(self, program: str, stdin: str = "") -> None:
        super().__init__(program, stdin)
        from esolangs.interpreters.register_based.between import _Machine

        self._machine = _Machine(program.splitlines(), self._io)

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
        return [v for v in self._machine.state.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        return []


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
    "Point Break": _PointBreakVM,
    "ArrowQueue": _ArrowQueueVM,
    "A Painter Ant": _APainterAntVM,
    "2dFish": _TwoDFishVM,
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
    "ABCDirection": _ABCDirectionVM,
    "Sophie": _SophieVM,
    "Jaune": _JauneVM,
    "SLOW ACV MAMMALIAN": _SlowAcvMammalianVM,
    "ZTOALC L": _ZtoalcLVM,
    "Between": _BetweenVM,
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
