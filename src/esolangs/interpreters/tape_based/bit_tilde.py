"""Interpreter for bit~.

An 8-cell bit pool with a pointer: ``~`` flips the current bit, ``>`` moves
the pointer right (extending the pool when the 8-cell window would run past
the end), ``<`` moves it left (a no-op at the first cell), ``)`` reads a
byte of input into the pool as 8 bits (MSB first, starting at the current
cell, extending the pool to hold the full window), ``(`` prints the 8-bit
window at the pointer as a byte, and ``{``/``}`` are a loop bracket pair:
``{`` jumps forward to the matching ``}`` when the current bit is zero and
``}`` jumps back to the matching ``{`` when it is nonzero.  Any other
character is ignored.

The pool is a single array that only ever grows: ``>`` appends a cell
whenever ``cell + 8`` would exceed the pool's length, and ``)`` pads the
pool to fit its window.  A ``(`` at a pointer with fewer than 8 cells left
prints just the available bits.

Semantics:
- ``)`` raises :class:`EOFError` when input runs out, where the cross-check
  exits with status 3 (the wiki leaves EOF undefined);
- a ``{``/``}`` whose match is missing raises :class:`ValueError` when it
  would have jumped (the former Ruby port
  looped forever);
- an empty input line yields no character (the cross-check would read a
  newline), so ``)`` on an empty line raises :class:`IndexError` through
  :meth:`esolangs.interpreters.io.IO.input_char`.

The interpreter runs on a :class:`_Machine` (the bit pool, the pointer, and
the code cursor), so it is step-capable: ``step()`` executes one character
and ``halted`` is true once the cursor reaches the end of the code.  A
bracket loop that returns to an exact state is a cycle the state-cycle hang
detector proves; the ``run()`` backstop stays for the unbounded-growth class
(a loop whose body keeps extending the pool).

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the code to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  The
pool is a tuple, so a state is a value that can be stored, compared, and
hashed as it stands.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what bit~ *does* stays in the
pure layer.  The two I/O characters are done by ``step`` before it calls the
pure transition, and the unmatched-bracket error is raised there too --
:func:`_match` is what can fail, so the shell resolves the jump first and
the transition receives a target it can simply take.
"""

from __future__ import annotations

import sys

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
    """Return ``tape`` extended with zeros to at least ``need`` cells.

    The pool only ever grows, and two commands grow it: ``>`` by one cell
    when the eight-cell window would run past the end, and ``)`` by however
    much its window needs.  Both come through here.
    """
    return tape if need <= len(tape) else (*tape, *([0] * (need - len(tape))))


def _match(code: str, ind: int, step: int) -> int:
    """Return the index of the bracket matching ``code[ind]``.

    ``step`` is 1 to find the forward ``}`` for a ``{`` and -1 to find the
    backward ``{`` for a ``}``; a bracket with no match is a malformed
    program (``ValueError``) — the cross-check loops forever instead.

    This is the one part of the language that can fail, which is why the
    shell calls it rather than the transition: :func:`_advance` is handed
    the resolved target and has no error case of its own.
    """
    depth = step
    while depth:
        ind += step
        if not 0 <= ind < len(code):
            raise ValueError("unmatched bit~ bracket")
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

    Pure, and total: the shell has already read any input byte and resolved
    any bracket jump, so every character it can be handed has a defined
    successor.  It takes no ``io`` argument, so ``)`` and ``(`` are the
    caller's business -- ``(`` changes no state at all, and ``)``'s byte
    arrives as ``byte``.

    ``target`` is the resolved bracket destination, already checked to
    exist.  It lands on the match because the shared increment below steps
    past it.

    Anything that is not a command is ignored and falls through to that
    same increment, which is what makes the cursor advance exactly once
    per call.
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
    """Per-run bit~ state: the bit pool, the pointer, and the cursor.

    ``step()`` executes one character; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object.
    """

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

        The two I/O characters and the unmatched-bracket error live here
        rather than in the transition: this is the shell, so it is where an
        effect or a raise belongs, and it leaves :func:`_advance` total.

        A bracket only searches for its match when it would actually jump,
        which is why the test is repeated here -- an unmatched bracket the
        program never jumps from is not an error.
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
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
