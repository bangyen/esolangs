"""6-5: a tape language spelled in digits.

A pointer walks a tape of integer cells that starts as one zero.  The
program is read left to right, one instruction at a time:

- ``5`` and ``6`` add 5 and 6 to the cell; ``2`` and ``9`` subtract them.
- ``1`` moves the pointer two cells right, ``3`` one cell left.
- ``A`` prints the cell as a character, ``B`` reads one into it.
- ``4`` is a marker.  ``8n`` jumps to the n-th marker, and ``7n`` skips the
  next instruction when the cell equals n.  The operand n is the next
  character, read as a digit: ``0``-``9``, then ``A``=10 onward.
- ``0`` halts, as does running off the end.  ``C`` starts a comment to the
  end of the line, and any other character is ignored.

The wiki names no failures, so: an ``8n`` with no n-th marker falls
through, and an ignored character is no instruction for ``7n`` to skip.
``3`` at the leftmost cell grows the tape a zero cell on the left: the spec
says nothing about the left edge, and cells left of the start are allowed.
Printing a cell outside the character range halts with
:class:`~esolangs.exceptions.HaltError`; exhausted input raises
:class:`EOFError`.
"""

from __future__ import annotations

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

#: The largest value ``A`` can print.  Outputting a cell outside the valid
#: character range is an invalid operation, not a wrap or a truncation.
_MAX_CHAR = 0x10FFFF

#: ``(ind, cell, tape)``: the token cursor, the cell pointer, and the tape,
#: a tuple so a state is a hashable value.  The tokens stay out: they never
#: change, and are a parameter to the transition instead.
type _State = tuple[int, int, tuple[int, ...]]

#: What each arithmetic instruction adds to the cell.
_ADD = {"5": 5, "6": 6, "2": -5, "9": -6}


def _operand(tok: str) -> int:
    """Return a ``7n``/``8n`` operand: a digit, then ``A``=10 onward.

    Any character decodes (a newline is -45); a ``7`` or ``8`` last in the
    program has none and reads 0.
    """
    if len(tok) < 2:
        return 0
    char = tok[1]
    return int(char) if char.isdigit() else ord(char.upper()) - 55


def _tokens(code: str) -> list[str]:
    """Split a program into instructions, merging each 7/8 with its operand.

    A ``C`` not operand to ``7``/``8`` starts a comment to end of line.
    Whitespace and other non-instructions are dropped, so ``7n`` "skips the
    next instruction", not a blank (``70 6`` skips the ``6``).
    """
    toks: list[str] = []
    i = 0
    while i < len(code):
        if code[i] == "C":
            # In ``78C`` the 8 is an operand, so C starts a comment.
            end = code.find("\n", i)
            if end < 0:
                break
            i = end
        elif code[i] in "78" and i + 1 < len(code):
            toks.append(code[i : i + 2])
            i += 2
        elif code[i] not in "0123456789AB":
            i += 1
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

    ``1`` moves right two and grows the tape; ``3`` moves back one, and at
    cell 0 grows the tape one zero cell on the left instead.  A missing
    ``8n`` marker leaves the cursor; ``0`` halts by putting it past the end.
    ``markers`` is :func:`_markers` of ``toks``.
    """
    ind, cell, tape = state
    tok = toks[ind]
    if tok == "1":
        cell += 2
        if len(tape) < cell + 1:
            tape = (*tape, *([0] * (cell + 1 - len(tape))))
    elif tok == "3":
        # At cell 0 the tape grows a zero cell on the left, and index 0 is
        # now that cell.  The spec says nothing about the left edge, and
        # cells left of the start are allowed.  The prepend
        # rebuilds the tuple, as ``1`` and every write already do.
        if cell:
            cell -= 1
        else:
            tape = (0, *tape)
    elif tok in _ADD:
        tape = _written(tape, cell, tape[cell] + _ADD[tok])
    elif tok[0] == "8":
        if markers is None:
            markers = _markers(toks)
        target = _marker(markers, _operand(tok))
        if target is not None:
            ind = target
    elif tok[0] == "7":
        if tape[cell] == _operand(tok):
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
    # qualifies for that protocol: ``3`` at cell 0 prepends a zero and
    # leaves the pointer at index 0, so ``ptr`` counts from the leftmost
    # cell and a period that grows left passes ``ptr == 0``, which the
    # certificate's ``m >= 1`` condition rejects; and every
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
        return self.io.progress()

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

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Not the state's order: reordering would change every stored hash.
        ind, cell, tape = self.state
        return (cell, tape, ind, self.io.progress())

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
                    f"{tape[cell]}, outside 0..{_MAX_CHAR}",
                    hint="keep the output cell between 0 and 1114111",
                )
            self.io.print_char(chr(tape[cell]))
        elif tok == "B":
            byte = self.io.input_char()
        self.state = _advance(self.state, self.toks, byte, self.markers)


def run(code: str, io: IO) -> None:
    """Run a 6-5 program."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
