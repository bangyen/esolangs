"""Interpreter for 6-5.

The wiki spec is authoritative: ``7n`` skips the *next instruction* when the
cell equals ``n`` (the value is a parameter, never executed), and ``8n`` is a
two-character token that jumps to the n-th ``4`` marker.  To get this right
the program is tokenized first, merging each ``7``/``8`` with its operand,
rather than reading the next character on the fly.

Outputting a cell value outside the valid character range is an invalid
operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the token list, the cell, the
tape, and the cursor), so it is step-capable: ``step()`` executes one token
and ``halted`` is true once the cursor reaches the end of the program,
making a ``8n`` jump back to a ``4`` marker a finite-state cycle the state
cycle detector can prove.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the token list to the next state, and
never mutates what it is given.  It takes no ``io`` argument at all, so it
is total and side-effect free by construction rather than by inspection.
The tape is a tuple, so a state is a value that can be stored, compared,
and hashed as it stands.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what 6-5 *does* stays in the
pure layer.  The two I/O tokens, and the out-of-range check that ``A``
halts on, stay in the shell -- which is what leaves the transition total.
"""

from __future__ import annotations

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: The largest value ``A`` can print.  Outputting a cell outside the valid
#: character range is an invalid operation, not a wrap or a truncation.
_MAX_CHAR = 0x10FFFF

#: One instant of a run: ``(ind, cell, tape)`` -- the token cursor, the cell
#: pointer, and the tape.  A value, not a record: every transition below
#: returns a new one rather than editing one in place, and the tape is a
#: ``tuple`` for the same reason.
#:
#: The tokens are deliberately not in here.  They do not change during a
#: run, so carrying them would put constant data in every value the cycle
#: detector stores.  They are a parameter to the transition instead.
#:
#: The field order starts ``ind`` for consistency with the other
#: interpreters, but ``snapshot`` still returns ``(cell, tape, ind, ...)``
#: -- the order it always returned.  Reordering there would silently
#: reorder every hash the cycle detector has stored.
type _State = tuple[int, int, tuple[int, ...]]


def num(char: str) -> int:
    """Decode a 6-5 operand digit: 0-9 literal, A-F hexadecimal."""
    if char.isdigit():
        return int(char)
    return ord(char.upper()) - 55


def _tokens(code: str) -> list[str]:
    """Split a program into instructions, merging each 7/8 with its operand.

    Comments start at a ``C`` that is not the operand of a ``7``/``8`` (a
    ``C`` after ``7``/``8`` is a value 12) and run to the end of the line.
    """
    code = re.sub(r"([^78])C[^\n]*", r"\1", code)
    toks: list[str] = []
    i = 0
    while i < len(code):
        if code[i] in "78" and i + 1 < len(code):
            toks.append(code[i : i + 2])
            i += 2
        else:
            toks.append(code[i])
            i += 1
    return toks


def _written(tape: tuple[int, ...], cell: int, value: int) -> tuple[int, ...]:
    """Return ``tape`` with ``cell`` set to ``value``."""
    return (*tape[:cell], value, *tape[cell + 1 :])


def _marker(toks: list[str], nth: int) -> int | None:
    """Return the index of the ``nth`` ``4`` marker, or None if absent.

    ``8n`` naming a marker the program does not have leaves the cursor
    where it is, so the miss is returned rather than raised -- which keeps
    the transition free of error cases.
    """
    count = 0
    for j, tok in enumerate(toks):
        if tok == "4":
            count += 1
            if count == nth:
                return j
    return None


def _advance(state: _State, toks: list[str], byte: int | None = None) -> _State:
    """Return the state after executing one token.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so ``A``'s print and ``B``'s read are the caller's business
    -- the print changes no state at all, and the read's byte arrives as
    ``byte``.

    ``1`` moves the pointer right by two and grows the tape to meet it;
    ``3`` moves back one and is clamped at the origin.  ``7n`` skips the
    next token when the cell equals ``n``, and ``8n`` jumps to the n-th
    ``4`` marker -- both operands are parameters, never executed, which is
    why the program was tokenized with them merged.

    ``0`` halts by putting the cursor past the last token, and returns
    early so the shared increment does not carry it further.
    """
    ind, cell, tape = state
    tok = toks[ind]
    if tok == "1":
        cell += 2
        if len(tape) < cell + 1:  # pragma: no branch - right moves always grow
            tape = (*tape, *([0] * (cell + 1 - len(tape))))
    elif tok == "3" and cell:
        cell -= 1
    elif tok in ("5", "6"):
        tape = _written(tape, cell, tape[cell] + int(tok))
    elif tok in ("2", "9"):
        tape = _written(tape, cell, tape[cell] - (int(tok) % 6 + 3))
    elif tok[0] == "8":
        target = _marker(toks, num(tok[1]) if len(tok) > 1 else 0)
        if target is not None:
            ind = target
    elif tok[0] == "7":
        if tape[cell] == (num(tok[1]) if len(tok) > 1 else 0):
            ind += 1  # skip the next instruction
    elif tok == "0":
        return (len(toks), cell, tape)  # halt
    elif tok == "B":
        tape = _written(tape, cell, byte if byte is not None else 0)
    return (ind + 1, cell, tape)


class _Machine:
    """Per-run 6-5 state: the tokens, cell, tape, and cursor.

    ``step()`` executes one token; ``halted`` is true once the cursor passes
    the last token.  A ``8n`` jump back to a ``4`` marker whose skip test
    never fires is a finite-state cycle the hang detector can prove.  The VM
    and the hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and reset the cell, tape, and cursor."""
        self.io = io
        self.toks = _tokens(code)
        # ``halted`` is read twice per token -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.toks)
        self.state: _State = (0, 0, (0,))

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
        """Whether the cursor has passed the last token."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Token tape + cursor; ip the cursor, memory the
    # cell tape.

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
        # The tape is already a tuple, so it goes in as it stands, in the
        # order this returned before the fields moved into a state value.
        ind, cell, tape = self.state
        return (cell, tape, ind, self.io.position())

    def step(self) -> None:
        """Execute one token, advancing the cursor.

        The two I/O tokens live here rather than in the transition: this is
        the shell, so it is where an effect belongs.  ``A``'s range check
        comes with the print, because it is what decides whether the effect
        can happen at all -- a cell outside the character range is an
        invalid operation, not a value to truncate.
        """
        if self.halted:
            return
        ind, cell, tape = self.state
        tok = self.toks[ind]
        byte = None
        if tok == "A":
            if not 0 <= tape[cell] <= _MAX_CHAR:
                raise HaltError
            self.io.print_char(chr(tape[cell]))
        elif tok == "B":
            byte = self.io.input_char()
        self.state = _advance(self.state, self.toks, byte)


def run(code: str, io: IO) -> None:
    """Run a 6-5 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
