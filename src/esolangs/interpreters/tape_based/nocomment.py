"""Interpreter for NoComment.

Byte tape with a wrapping pointer (size 4096; ``run`` takes ``tape``) plus
a byte stack.  ``i``/``d``/``c`` increment/decrement/clear, ``l``/``r``
move, ``n``/``f`` push/pop, ``s``/``b`` jump forward X/back X-1 by the
peeked stack top when the cell is nonzero, ``o`` prints.  Per the wiki, a
non-command character is malformed (:class:`ValueError`) and popping or
peeking an empty stack halts (:class:`~esolangs.exceptions.HaltError`).

:func:`_advance` is a pure, total transition over an immutable ``_State``
with no ``io`` argument; :class:`_Machine` is the shell that prints and
raises.
"""

from __future__ import annotations

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

# Finite by specification: the wiki defines pointer overflow as moving "to
# the opposite end of memory" and says "the memory space needs to be static".
# The size is a host choice, and observable (cell 0 steps left to tape - 1),
# so changing the default changes what wrapping programs do.
_TAPE = 4096

#: ``(ind, ptr, tape, stack, acc, dirty)``: an immutable value, rebound per
#: step.  ``acc`` is the true cell under the pointer; while ``dirty``,
#: ``tape[ptr]`` is stale and :func:`_committed` (every path that leaves the
#: cell) fixes it.  ``snapshot`` and ``tape`` commit first, so one logical
#: state has one spelling for the cycle detector.
#: The buffer is what makes a static 4096-cell immutable tape affordable: the
#: text corpus writes one cell 111 times before moving, so 111 rebuilds
#: become one (brainfuck's buffer; RAM0 writes distinct addresses, so it
#: would absorb nothing there).
#: ``bytes``, not a tuple: the boolean corpus has no runs (write, then move;
#: ~66% of steps commit), and a ``bytes`` rebuild is one memcpy vs 4096
#: pointer copies -- 32x over the 2637 commits of an 11-input decode
#: (44.6ms -> 1.4ms).  Cells are mod-256, and ``bytes`` stays hashable.
type _State = tuple[int, int, bytes, tuple[int, ...], int, bool]


def _committed(state: _State) -> bytes:
    """Return ``state``'s tape with the buffered cell written back if stale."""
    _ind, ptr, tape, _stack, acc, dirty = state
    if not dirty:
        return tape
    return tape[:ptr] + bytes((acc,)) + tape[ptr + 1 :]


def _advance(state: _State, code: str, size: int) -> _State:
    """Return the state after executing the command at the cursor.

    Total: the shell has already rejected underflow, out-of-range jumps and
    unknown characters.  ``s``/``b`` peek the stack and fire only on nonzero.
    """
    ind, ptr, tape, stack, acc, dirty = state
    char = code[ind]
    if char == "i":
        # Buffered; the tape is untouched.
        acc = (acc + 1) % 256
        dirty = True
    elif char == "d":
        acc = (acc - 1) % 256
        dirty = True
    elif char == "c":
        acc = 0
        dirty = True
    elif char in "lr":
        # Leaving the cell: commit first.  Wraps at both ends, per the wiki.
        tape = _committed(state)
        dirty = False
        ptr = (ptr + (1 if char == "r" else -1)) % size
        acc = tape[ptr]
    elif char == "n":
        stack = (*stack, acc)
    elif char == "f":
        acc, stack = stack[-1], stack[:-1]
        dirty = True
    elif char in "sb" and acc and stack:
        ind += stack[-1] if char == "s" else -stack[-1]
    return (ind + 1, ptr, tape, stack, acc, dirty)


class _Machine:
    """Per-run NoComment state: the byte tape, the stack, and the cursor."""

    def __init__(self, code: str, io: IO, tape: int = _TAPE) -> None:
        """Start with a cleared tape of ``tape`` cells at the origin."""
        if tape < 1:
            raise ValueError(f"the NoComment tape needs at least one cell, got {tape}")
        self.io = io
        self.code = code
        self.size = tape
        # ``halted`` is read twice per command; take the length once.
        self.length = len(code)
        self.state: _State = (0, 0, bytes(tape), (), 0, False)

    # Views on the state.  ``tape`` and ``snapshot`` commit first.

    @property
    def tape(self) -> tuple[int, ...]:
        # Widen ``bytes`` to a cell tuple here, not in the hot path.
        return tuple(_committed(self.state))

    @property
    def stack(self) -> tuple[int, ...]:
        return self.state[3]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.length

    # VM view.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The tape's cells."""
        return list(self.tape)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Committed tape (one spelling per state), as ``bytes``: it hashes by
        # value, and widening 4096 cells per step would cost more than the
        # commit the buffer exists to avoid.
        ind, ptr, _tape, stack, _acc, _dirty = self.state
        return (_committed(self.state), stack, ptr, ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        ``o`` reads the write buffer ``acc``, the cell's true value whether or
        not the tape has caught up.
        """
        if self.halted:
            return
        ind, _ptr, _tape, stack, acc, _dirty = self.state
        char = self.code[ind]
        if char == "f" and not stack:
            raise HaltError(
                f"'f' at position {ind} pops the stack and the stack is empty"
            )
        if char in "sb" and acc and not stack:
            raise HaltError(
                f"{char!r} at position {ind} peeks the stack and the stack is empty"
            )
        if char in "sb" and acc and stack:
            # ``s`` skips X forward, ``b`` jumps back X-1: next is ind ± X + 1.
            # One check for both, or each direction leaves a dead branch.
            delta = stack[-1] if char == "s" else -stack[-1]
            if not 0 <= ind + delta + 1 < self.length:
                raise HaltError(
                    f"{char!r} at position {ind} jumps {delta:+d} to "
                    f"{ind + delta + 1}, outside the program's 0..{self.length - 1}"
                )
        elif char == "o":
            self.io.print_char(chr(acc))
        elif char not in "idclrnfsb":
            raise ValueError(f"unrecognized NoComment command {char!r}")
        self.state = _advance(self.state, self.code, self.size)


def run(code: str, io: IO, tape: int = _TAPE) -> None:
    """Run a NoComment program on a tape of ``tape`` cells."""
    machine = _Machine(code, io, tape)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
