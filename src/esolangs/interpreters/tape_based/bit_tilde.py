"""Interpreter for bit~.

An 8-cell bit pool with a pointer: ``~`` flips, ``>``/``<`` move (``>``
extends the pool when the window would run past the end; ``<`` is a
no-op at cell 0), ``)`` reads a byte as 8 bits MSB first, ``(`` prints
the 8-bit window (fewer if the pool ends), ``{``/``}`` loop on the
current bit.  Other characters are ignored.  ``)`` raises
:class:`EOFError` on exhausted input (the cross-check exits 3); an
unmatched bracket raises :class:`ValueError` when it would jump (the
Ruby port looped); an empty line delivers its newline, so ``)`` reads 10.
:func:`_advance` is pure over an immutable ``_State``; the shell reads,
prints and resolves the jump via :func:`_match`, the one part that can
fail.  A loop that keeps extending the pool never repeats; ``run()``'s
backstop covers it.
"""

from __future__ import annotations

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.brackets import unmatched
from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, cell, tape)`` -- the code cursor, the
#: pointer, and the bit pool.  A value, not a record: every transition below
#: returns a new one rather than editing one in place, and the pool is a
#: ``tuple`` for the same reason.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
#:
#: The field order starts ``ind, cell`` for readability, but ``snapshot``
#: still returns ``(tape, cell, ind, ...)`` -- the order it always returned.
#: Reordering there would silently reorder every stored hash.
type _State = tuple[int, int, tuple[int, ...]]


def _grown(tape: tuple[int, ...], need: int) -> tuple[int, ...]:
    """Return ``tape`` extended with zeros to at least ``need`` cells."""
    return tape if need <= len(tape) else (*tape, *([0] * (need - len(tape))))


def _match(code: str, ind: int, step: int) -> int:
    """Return the index of the bracket matching ``code[ind]``.

    ``step`` 1 forward, -1 back; no match is ``ValueError``.
    """
    start = ind
    depth = step
    while depth:
        ind += step
        if not 0 <= ind < len(code):
            # The scan walks away from the bracket, so the position named
            # is the one it started from -- the bracket that has no match,
            # not wherever the walk fell off the code.
            raise unmatched(code[start], start)
        if code[ind] == "{":
            depth += 1
        elif code[ind] == "}":
            depth -= 1
    return ind


def _advance(
    state: _State,
    code: str,
    byte: int | None = None,
    target: int | None = None,
) -> _State:
    """Return the state after executing the character at the cursor.

    Pure and total: the shell has read the byte and resolved ``target``,
    which lands on the match because the shared increment steps past it.
    """
    ind, cell, tape = state
    char = code[ind]
    if char == "~":
        tape = (*tape[:cell], tape[cell] ^ 1, *tape[cell + 1 :])
    elif char == ">":
        # The window is eight cells wide, so the pool grows to keep one.
        if cell + 8 > len(tape):
            tape = (*tape, 0)
        cell += 1
    elif char == "<":
        # ``<`` at the first cell is a no-op rather than an error.
        if cell:
            cell -= 1
    elif char == ")":
        bits = tuple(int(b) for b in f"{byte if byte is not None else 0:08b}")
        tape = _grown(tape, cell + 8)
        tape = (*tape[:cell], *bits, *tape[cell + 8 :])
    elif target is not None:
        # Both brackets, once the shell has decided a jump happens.
        ind = target
    return (ind + 1, cell, tape)


class _Machine:
    """Per-run bit~ state: the bit pool, the pointer, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Start with an eight-cell pool at the origin."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per character -- once by ``run``'s loop
        # and once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, 0, (0,) * 8)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def cell(self) -> int:
        return self.state[1]

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Bit pool + pointer; ip the cursor, memory the pool.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

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
        # The pool is already a tuple, so it goes in as it stands, in the
        # order this returned before the fields moved into a state value.
        ind, cell, tape = self.state
        return (tape, cell, ind, self.io.position())

    def step(self) -> None:
        """Execute one character, advancing the cursor.

        The shell does I/O and the bracket search, only when the bracket would jump.
        """
        if self.halted:
            return
        ind, cell, tape = self.state
        char = self.code[ind]
        byte = target = None
        if char == ")":
            byte = self.io.input_char()
        elif char == "(":
            val = tape[cell : cell + 8]
            self.io.print_char(chr(int("".join(map(str, val)), 2)))
        elif char == "{" and not tape[cell]:
            target = _match(self.code, ind, 1)
        elif char == "}" and tape[cell]:
            target = _match(self.code, ind, -1)
        self.state = _advance(self.state, self.code, byte, target)


def run(code: str, io: IO) -> None:
    """Run a bit~ program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
