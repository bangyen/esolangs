"""Interpreter for Home Row.

BF-like over a 5x5 wrapping grid of unbounded cells: ``a``/``s`` add and
subtract 1, ``d``/``f`` move down/right mod 5, ``j`` skips the next
instruction on a zero cell, ``k`` prints the cell as a byte and zeroes
it, a pair of ``l``s is a while-nonzero loop, ``;`` ends the program.
Decisions: cells are unbounded (the wiki's Minsky construction needs
it), so ``k`` prints the low byte and ``s`` on 0 gives -1 (the talk page
asks, the author never ruled); the end of the source halts; ``l`` pairs
alternate by order (first with second, third with fourth), and a
trailing unpaired ``l`` raises :class:`ValueError`.  :func:`_advance` is
pure over an immutable ``_State``; ``k``'s print is the shell's, its
clearing the transition's.  The 25-cell grid is cheap to rebuild, so no
write buffer.
"""

from __future__ import annotations

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.brackets import unmatched
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
        # One glyph both opens and closes here, so the pairing cannot come
        # from `match_brackets`; the rejection is still the shared one.
        raise unmatched("l", stack[-1])
    return match, open_l


def _advance(
    state: _State,
    code: str,
    match: dict[int, int],
    open_l: set[int],
) -> _State:
    """Return the state after executing the command at the cursor.

    ``d`` moves five cells mod 25; ``f`` wraps within its row (a torus).
    An opening ``l`` jumps past its partner on zero, a closing one back on
    nonzero.
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
    """Per-run Home Row state: the grid, pointer, and code cursor."""

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

        ``k``'s print is here; its clearing is the transition's.
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
    script_main(run)
