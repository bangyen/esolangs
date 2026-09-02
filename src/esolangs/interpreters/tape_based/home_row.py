"""Interpreter for Home Row.

A BF-like language over a 5x5 wrapping grid of unbounded cells (the torus
the wiki describes).  ``a``/``s`` add/subtract 1 to the current cell,
``d``/``f`` move the pointer down/right (wrapping mod 5), ``j`` skips the
next instruction when the current cell is zero, ``k`` prints the current
cell as a byte and resets it to zero, a pair of ``l``s is a while-nonzero
loop ("runs if the current memory spot is nonzero and reruns after the
second l each time if the current memory spot is nonzero"), and ``;`` ends
the program.  The pointer starts at the top-left cell.

Documented decisions for gaps and divergences:
- cells are unbounded integers (the wiki's Minsky-machine construction needs
  unbounded registers), so ``k`` prints the low byte and ``s`` on a 0 cell
  yields -1 (the wiki's talk page asks whether decrementing 0 should be a
  no-op, but the language's author never ruled; the main page says ``s``
  subtracts 1, so the cell goes negative);
- reaching the end of the source without ``;`` halts (the pointer has no
  direction to keep moving);
- ``l`` pairs alternate by their order in the program (the first and second
  ``l`` form a loop, the third and fourth form another, and so on), matching
  the RISC-V compiler's ``loop // 2`` numbering rather than BF-style
  nesting; an unbalanced trailing ``l`` is a malformed program
  (:class:`ValueError`).

The interpreter runs on a :class:`_Machine` (the fixed 25-cell grid, the
pointer, and the code cursor), so it is step-capable: ``step()`` executes
one command and ``halted`` is true once the cursor reaches the end of the
program or hits ``;``.  A loop whose body never changes the tested cell
(e.g. ``all``: increment once, then loop on a cell the body never touches)
is a genuine state cycle a repeated :meth:`_Machine.snapshot` proves; a
loop that keeps incrementing the tested cell is unbounded growth and needs
the wall-clock backstop instead.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the loop pairing to the next state, and
never mutates what it is given.  It takes no ``io`` argument at all, so it
is total and side-effect free by construction rather than by inspection.
The grid is a tuple, so a state is a value that can be stored, compared,
and hashed as it stands.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Home Row *does* stays in
the pure layer.  ``k``'s print is the language's only effect and is done by
``step`` before it calls the pure transition -- the *clearing* half of
``k`` stays in the transition, since that is a state change, not an effect.

The grid is a fixed 25 cells, so rebuilding it per write is cheap and this
needs no write buffer -- unlike NoComment, whose static 4096-cell tape does.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, ptr, grid)`` -- the code cursor, the
#: pointer, and the 25 cells.  A value, not a record: every transition below
#: returns a new one rather than editing one in place, and the grid is a
#: ``tuple`` for the same reason.
#:
#: This is exactly what ``snapshot`` returns, and always has been, so the
#: state and its hashable view are the same tuple.
#:
#: The code and its loop pairing are deliberately not in here.  Neither
#: changes during a run, so carrying them would put constant data in every
#: value the cycle detector stores.  They are parameters to the transition.
type _State = tuple[int, int, tuple[int, ...]]


def _matches(code: str) -> tuple[dict[int, int], set[int]]:
    """Return ``{l: partner}`` and the set of loop-open indices."""
    stack: list[int] = []
    match: dict[int, int] = {}
    open_l: set[int] = set()
    for i, char in enumerate(code):
        if char != "l":
            continue
        if not stack:
            stack.append(i)
            open_l.add(i)
        else:
            j = stack.pop()
            match[i] = j
            match[j] = i
    if stack:
        raise ValueError(f"unmatched 'l' at position {stack[-1]}")
    return match, open_l


def _advance(
    state: _State,
    code: str,
    match: dict[int, int],
    open_l: set[int],
) -> _State:
    """Return the state after executing the command at the cursor.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so ``k``'s print is the caller's business -- but ``k`` also
    *clears* the cell it printed, and that half belongs here, because it is
    a state change rather than an effect.

    ``d`` moves down a row (five cells, mod 25) and ``f`` moves right within
    the current row, wrapping back to that row's first cell rather than
    spilling into the next -- which is what makes the grid a torus in both
    axes rather than a flat 25-cell line.

    ``l`` pairs alternate by their order in the program, so which of a pair
    a cursor sits on decides the direction of the test: an opening ``l``
    jumps past its partner on a zero cell, and a closing one jumps back on
    a nonzero cell.

    Anything else is a no-op and falls through to the shared increment.
    """
    ind, ptr, grid = state
    char = code[ind]
    if char == "a":
        grid = (*grid[:ptr], grid[ptr] + 1, *grid[ptr + 1 :])
    elif char == "s":
        # Cells are unbounded, so ``s`` on a zero cell yields -1.
        grid = (*grid[:ptr], grid[ptr] - 1, *grid[ptr + 1 :])
    elif char == "d":
        ptr = (ptr + 5) % 25
    elif char == "f":
        ptr += 1
        if ptr % 5 == 0:
            ptr -= 5
    elif char == "j":
        # Skip the next command when the current cell is zero.
        if grid[ptr] == 0:
            ind += 1
    elif char == "k":
        # The print already happened in the shell; this is the clear.
        grid = (*grid[:ptr], 0, *grid[ptr + 1 :])
    elif char == "l":
        partner = match[ind]
        if ind in open_l:
            if grid[ptr] == 0:
                ind = partner
        elif grid[ptr] != 0:
            ind = partner
    return (ind + 1, ptr, grid)


class _Machine:
    """Per-run Home Row state: the grid, pointer, and code cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the program or hits ``;``.  The state-cycle hang
    detector and the VM expose this object.
    """

    __slots__ = ("code", "io", "match", "open_l", "size", "state")

    def __init__(self, code: str, io: IO) -> None:
        """Match ``code``'s loop pairs and start the grid at all zeros."""
        self.io = io
        self.code = code
        self.match, self.open_l = _matches(code)
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, 0, (0,) * 25)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def grid(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def halted(self) -> bool:
        """Whether the cursor has run off the program or hit ``;``."""
        ind = self.state[0]
        return ind >= self.size or self.code[ind] == ";"

    # The VM's language-shaped view: 5x5 torus grid + pointer; ip the cursor, memory
    # the 25 cells.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.state[2])

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The state as it stands: it is already the (ind, ptr, grid) triple
        # this returned before the split, and it is already hashable.
        return self.state

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        ``k``'s print is here rather than in the transition: this is the
        shell, so it is where an effect belongs.  Only the print, though --
        ``k`` also clears the cell, and the transition does that, so the
        two halves land on the right side of the split.
        """
        if self.halted:
            return
        ind, ptr, grid = self.state
        if self.code[ind] == "k":
            self.io.print_char(chr(grid[ptr] & 0xFF))
        self.state = _advance(self.state, self.code, self.match, self.open_l)


def run(code: str, io: IO) -> None:
    """Run a Home Row program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
