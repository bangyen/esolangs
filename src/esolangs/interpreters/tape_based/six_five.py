"""Interpreter for 6-5.

Per the wiki, ``7n`` skips the next instruction when the cell equals
``n`` and ``8n`` jumps to the n-th ``4`` marker; both operands are
parameters, so the program is tokenized with them merged.  Printing a
cell outside the character range halts with
:class:`~esolangs.exceptions.HaltError`; exhausted input raises
:class:`EOFError`.

:func:`_advance` is a pure transition over an immutable ``_State`` (tuple
tape, so hashable) with no ``io`` argument; :class:`_Machine` is the shell
holding the two I/O tokens and ``A``'s range check.
"""

from __future__ import annotations

import re

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
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

    A ``C`` not operand to ``7``/``8`` starts a comment to end of line.
    """
    # Lookbehind, not a captured character: ``([^78])C`` needed a character
    # before the ``C``, so a comment on the first line (``C...``) survived.
    code = re.sub(r"(?<![78])C[^\n]*", "", code)
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


def _markers(toks: list[str]) -> tuple[int, ...]:
    """Return the index of every ``4`` marker, in program order."""
    return tuple(j for j, tok in enumerate(toks) if tok == "4")


def _marker(markers: tuple[int, ...], nth: int) -> int | None:
    """Return the index of the ``nth`` ``4`` marker, or None if absent."""
    if 1 <= nth <= len(markers):
        return markers[nth - 1]
    return None


def _advance(
    state: _State,
    toks: list[str],
    byte: int | None = None,
    markers: tuple[int, ...] | None = None,
) -> _State:
    """Return the state after executing one token.

    ``1`` moves right two and grows the tape; ``3`` moves back one, clamped
    at 0.  A missing ``8n`` marker leaves the cursor; ``0`` halts by putting
    it past the end.  ``markers`` is :func:`_markers` of ``toks``.
    """
    ind, cell, tape = state
    tok = toks[ind]
    if tok == "1":
        cell += 2
        if len(tape) < cell + 1:
            tape = (*tape, *([0] * (cell + 1 - len(tape))))
    elif tok == "3" and cell:
        cell -= 1
    elif tok in ("5", "6"):
        tape = _written(tape, cell, tape[cell] + int(tok))
    elif tok in ("2", "9"):
        tape = _written(tape, cell, tape[cell] - (int(tok) % 6 + 3))
    elif tok[0] == "8":
        if markers is None:
            markers = _markers(toks)
        target = _marker(markers, num(tok[1]) if len(tok) > 1 else 0)
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
    """Per-run 6-5 state: the tokens, cell, tape, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and reset the cell, tape, and cursor."""
        self.io = io
        self.toks = _tokens(code)
        # ``halted`` is read twice per token -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.toks)
        self.markers = _markers(self.toks)
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

    # The growth detector's view.  The pointer is ``cell`` here, so it is
    # aliased to the name ``esolangs.vm._TapeMachine`` asks for.  6-5
    # qualifies for that protocol: ``3`` clamps at the left edge exactly as
    # brainfuck's ``<`` does (``elif tok == "3" and cell``), which is what
    # the certificate's ``m >= 1`` condition is written against, and every
    # other command reads or writes only ``tape[cell]``.  ``1`` moves *two*
    # cells and appends two zeros rather than one; that is still fresh
    # rightward growth, and the certificate checks the tape grew by exactly
    # the displacement rather than by one.

    @property
    def ptr(self) -> int:
        """The cell pointer, under the name the growth detector reads."""
        return self.state[1]

    def input_position(self) -> int:
        """Report the input cursor for the growth detector."""
        return self.io.position()

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

        ``A``'s range check is here with the print: an out-of-range cell is an
        invalid operation, not a value to truncate.
        """
        if self.halted:
            return
        ind, cell, tape = self.state
        tok = self.toks[ind]
        byte = None
        if tok == "A":
            if not 0 <= tape[cell] <= _MAX_CHAR:
                raise HaltError(
                    f"'A' prints cell {cell} as a character and it holds "
                    f"{tape[cell]}, outside 0..{_MAX_CHAR}"
                )
            self.io.print_char(chr(tape[cell]))
        elif tok == "B":
            byte = self.io.input_char()
        self.state = _advance(self.state, self.toks, byte, self.markers)


def run(code: str, io: IO) -> None:
    """Run a 6-5 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
