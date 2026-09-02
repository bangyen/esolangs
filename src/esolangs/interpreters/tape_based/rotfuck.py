"""Interpreter for ROTfuck.

Brainfuck whose program text rotates: every executed command advances all
non-comment characters one step along the cyclic alphabet ``+-><,.[]``
(``+`` becomes ``-``, ``-`` becomes ``>``, ..., ``]`` becomes ``+``).  The
command at the instruction pointer is therefore a function of how many
commands have run, not just of the source text.

A character outside the alphabet is a comment: the pointer passes over it
without executing it, and -- since the wiki rotates "every time an
instruction is executed" and a comment is not an instruction -- without
rotating the program.  Comments are therefore fully transparent, and the
same program with or without them behaves identically.  This is the
package's reading rather than something the wiki states outright: the page
never defines what counts as a comment, and ROTfuck has no reference
implementation to defer to.  The reading matters, because the alternative
(rotating on comments too) would make whitespace significant and mean a
program could not be reformatted at all.

The tape follows the same conventions as the plain Brainfuck interpreter in
this package: an 8-bit wrapping tape that grows to the right, ``<`` clamped
at the left edge, and :class:`EOFError` when ``,`` runs out of input.

Brackets are matched dynamically.  Because the rotation changes which
character sits at each position, a bracket's partner cannot be fixed in
advance from the source; instead, when a bracket needs to jump it rotates
the program first (the rotation is the bracket's side effect of executing)
and then seeks for the matching bracket in the rotated program, using the
standard nesting count.  A bracket that fires with no partner in the rotated
program is a runtime error, not a load error, and the interpreter halts with
:class:`~esolangs.exceptions.HaltError`.  Unbalanced sources are legal, since
the rotation can bring any character to the pointer at any time; only
executing a partnerless bracket is an error.

Rather than physically rotating the whole program after every command (an
O(n) rewrite per step), the interpreter tracks the rotation count and
derives the effective character at any position on the fly: after ``k``
rotations the command at a source position has advanced ``k`` steps along
the cycle.  Bracket partners are found by the same derivation, so the
behavior is identical to rotating the program text.
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


def _at(chars: tuple[str, ...], rot: int, i: int) -> str:
    """Return the effective command at ``i`` under rotation ``rot``.

    A comment never rotates and never changes, so it reads as itself.
    """
    ch = chars[i]
    if ch in _COMMANDS:
        return _CYCLE[(_CYCLE.index(ch) + rot) % len(_CYCLE)]
    return ch


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
    """A ROTfuck program with an implicit rotation count.

    The source text is stored once; the effective command at position ``i``
    after ``rot`` executed commands is the source character advanced ``rot``
    steps along the cycle (comments never rotate).  Matching a bracket seeks
    through these effective characters with the standard nesting count.
    """

    def __init__(self, code: str) -> None:
        """Store ``code`` with a zero rotation count."""
        self._chars = list(code)
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
        return tuple(self._chars)

    def at(self, i: int) -> str:
        """Return the effective command at ``i`` under the current rotation."""
        return _at(self.chars(), self._rot, i)


def _advance(state: _State, chars: tuple[str, ...], byte: int | None = None) -> _State:
    """Return the state after executing the command under the cursor.

    Pure: it reads ``state`` and returns a new one.  ``.``'s printing is
    the caller's business -- the cell it prints is carried forward
    unchanged -- and ``,``'s byte arrives as ``byte``.

    A bracket that jumps rotates *before* seeking its partner, so the
    partner is looked up in the program the jump lands in rather than the
    one it left.  Both jumps land one past the partner.

    A comment advances the cursor without rotating: the spec rotates
    "every time an instruction is executed", and a comment is passed over,
    not executed.  A bracket whose guard is false does rotate -- it is an
    executed instruction that simply did not jump.
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
        tape = (*tape[:ptr], byte if byte is not None else 0, *tape[ptr + 1 :])
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

    ``step()`` executes one command (rotating the program as its side
    effect); ``halted`` is true once the cursor reaches the end of the
    source.  The rotation count, tape, and cursor fully determine the next
    command, so a program that revisits them is a finite-state cycle the
    hang detector can prove.  The VM and the hang detector expose this
    object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with an empty tape at the origin and a fresh program."""
        self.io = io
        self.prog = _Program(code)
        self.tape: list[int] = [0]
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
            tuple(self.tape),
            self.ptr,
            self.ind,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (tuple(self.tape), self.ptr, self.ind, self.prog.rotation())

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- the VM's views and
        the tests read them -- so they stay, and the rotation goes back
        through _Program, which is what ``at`` consults.
        """
        tape, self.ptr, self.ind, rot = state
        self.tape = list(tape)
        self.prog.set_rotation(rot)

    def step(self) -> None:
        """Execute one command, advancing the cursor and rotation.

        The two ports live here rather than in the transition: this is the
        shell.  ``.`` prints the cell the transition carries forward
        unchanged, and ``,``'s byte is read here and handed over.  Which
        command a cell *is* depends on the rotation, so both consult the
        effective character rather than the source one.
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
