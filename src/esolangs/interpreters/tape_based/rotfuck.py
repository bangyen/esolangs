"""Interpreter for ROTfuck.

Brainfuck whose program rotates: every executed command advances all
non-comment characters one step along ``+-><,.[]``.  A comment is passed
over without rotating (the wiki rotates "every time an instruction is
executed"; the alternative would make whitespace significant) -- the
package's reading, since the page defines no comment.  Tape as plain
Brainfuck: 8-bit, ``<`` clamped, :class:`EOFError` on exhausted input.
Brackets match dynamically: a jumping bracket rotates first, then seeks
its partner in the rotated program; a partnerless bracket that fires
raises :class:`~esolangs.exceptions.HaltError`, and unbalanced sources
are legal.  The rotation count is tracked and the effective character
derived, not the text rewritten.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_CYCLE = "+-><,.[]"
_COMMANDS = frozenset(_CYCLE)


#: One instant of a run: ``(tape, ptr, ind, rot)`` -- the cells, the cell
#: pointer, the cursor, and how many commands have executed.  A value
#: :func:`_advance` maps forward, with the tape as a ``tuple``.
#:
#: ``rot`` is the language.  The source text never changes, but the
#: *effective* command at a position is its character advanced ``rot``
#: steps along the cycle, so the rotation count is what a step is really
#: reading -- which is why it belongs in the state and the characters do
#: not.
type _State = tuple[tuple[int, ...], int, int, int]


#: Each command's index in ``_CYCLE``, so the rotation is an addition rather
#: than a ``str.index`` scan.  A command's effective character after ``rot``
#: steps is ``_CYCLE[(_OPCODE[ch] + rot) % 8]``; the dict doubles as the
#: membership test, since a comment is exactly a character it does not hold.
_OPCODE = {ch: i for i, ch in enumerate(_CYCLE)}


def _at(chars: tuple[str, ...], rot: int, i: int) -> str:
    """Return the effective command at ``i`` under rotation ``rot``.

    Arithmetic on a precomputed opcode: the hottest function, and a cycle
    scan was 46% of a generated program's runtime.
    """
    code = _OPCODE.get(chars[i], -1)
    return _CYCLE[(code + rot) % 8] if code >= 0 else chars[i]


def _forward(chars: tuple[str, ...], rot: int, i: int) -> int | None:
    """Return the ``]`` matching the effective ``[`` at ``i``, if any."""
    depth = 1
    j = i + 1
    while j < len(chars):
        ch = _at(chars, rot, j)
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return None


def _backward(chars: tuple[str, ...], rot: int, i: int) -> int | None:
    """Return the ``[`` matching the effective ``]`` at ``i``, if any."""
    depth = 1
    j = i - 1
    while j >= 0:
        ch = _at(chars, rot, j)
        if ch == "]":
            depth += 1
        elif ch == "[":
            depth -= 1
            if depth == 0:
                return j
        j -= 1
    return None


class _Program:
    """A ROTfuck program with an implicit rotation count."""

    def __init__(self, code: str) -> None:
        """Store ``code`` with a zero rotation count."""
        # The source never changes -- only the rotation count does -- so the
        # tuple every caller wants is built once here rather than per
        # lookup.  It was rebuilt on each ``at`` call, an O(len(code)) copy
        # to read one character, which alone was 15% of a run.
        self._chars = tuple(code)
        self._rot = 0

    def rotate(self) -> None:
        """Advance the rotation count by one (a command executed)."""
        self._rot += 1

    def rotation(self) -> int:
        """Return how many commands have executed (the implicit rotation)."""
        return self._rot

    def set_rotation(self, rot: int) -> None:
        """Set the rotation count, for a caller that computed it elsewhere."""
        self._rot = rot

    def chars(self) -> tuple[str, ...]:
        """Return the unrotated source characters."""
        return self._chars

    def at(self, i: int) -> str:
        """Return the effective command at ``i`` under the current rotation."""
        return _at(self._chars, self._rot, i)


def _advance(state: _State, chars: tuple[str, ...], byte: int | None = None) -> _State:
    """Return the state after executing the command under the cursor.

    A bracket rotates *before* seeking, and lands one past the partner.  A
    comment advances without rotating; a false-guarded bracket does rotate.
    """
    tape, ptr, ind, rot = state
    char = _at(chars, rot, ind)

    if char == ">":
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
    elif char == "<":
        if ptr:
            ptr -= 1
    elif char == "+":
        tape = (*tape[:ptr], (tape[ptr] + 1) % 256, *tape[ptr + 1 :])
    elif char == "-":
        tape = (*tape[:ptr], (tape[ptr] - 1) % 256, *tape[ptr + 1 :])
    elif char == ",":
        # Reduced like ``+`` and ``-`` above.  ``input_char`` returns a
        # whole code point, so an input line starting above U+00FF
        # otherwise put that code point on the 8-bit tape this module's
        # docstring describes, and left the cell disagreeing with itself:
        # the next ``+`` reduced what ``,`` had not.
        tape = (
            *tape[:ptr],
            (byte if byte is not None else 0) % 256,
            *tape[ptr + 1 :],
        )
    elif char == "[" and tape[ptr] == 0:
        rot += 1
        partner = _forward(chars, rot, ind)
        if partner is None:
            raise HaltError("an executed '[' has no bracket partner")
        return (tape, ptr, partner + 1, rot)
    elif char == "]" and tape[ptr] != 0:
        rot += 1
        partner = _backward(chars, rot, ind)
        if partner is None:
            raise HaltError("an executed ']' has no bracket partner")
        return (tape, ptr, partner + 1, rot)

    if char in _COMMANDS:
        rot += 1
    return (tape, ptr, ind + 1, rot)


class _Machine:
    """Per-run ROTfuck state: the rotating program, tape, pointer, and cursor.

    Rotation, tape and cursor determine the next command, so a revisit is a cycle.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with an empty tape at the origin and a fresh program."""
        self.io = io
        self.prog = _Program(code)
        self.tape: tuple[int, ...] = (0,)
        self.ptr = 0
        self.ind = 0
        self._size = len(code)

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the source."""
        return self.ind >= self._size

    # The VM's language-shaped view: Rotating tape + cursor; ip the cursor, memory the
    # tape.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.prog.rotation(),
            self.tape,
            self.ptr,
            self.ind,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.tape, self.ptr, self.ind, self.prog.rotation())

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        ``tape`` stays the immutable tuple (a list was converted for no one).
        """
        self.tape, self.ptr, self.ind, rot = state
        self.prog.set_rotation(rot)

    def step(self) -> None:
        """Execute one command, advancing the cursor and rotation.

        Both ports consult the effective character, not the source one.
        """
        if self.halted:
            return
        char = self.prog.at(self.ind)

        byte = None
        if char == ".":
            self.io.print_char(chr(self.tape[self.ptr]))
        elif char == ",":
            byte = self.io.input_char()

        chars = self.prog.chars()
        try:
            self._restore(_advance(self._state, chars, byte))
        except HaltError:
            # A jumping bracket rotates before it seeks, so a partnerless
            # one leaves the rotation advanced even though it never moved.
            # The original mutated the program first and raised second;
            # keeping that means recording the rotation on the way out.
            self.prog.rotate()
            raise


def run(code: str, io: IO) -> None:
    """Run a ROTfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
