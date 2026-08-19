"""Interpreter for ROTfuck.

Brainfuck whose program text rotates: every executed command advances all
non-comment characters one step along the cyclic alphabet ``+-><,.[]``
(``+`` becomes ``-``, ``-`` becomes ``>``, ..., ``]`` becomes ``+``).  The
command at the instruction pointer is therefore a function of how many
commands have run, not just of the source text.

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

    def at(self, i: int) -> str:
        """Return the effective command at ``i`` under the current rotation."""
        ch = self._chars[i]
        if ch in _COMMANDS:
            return _CYCLE[(_CYCLE.index(ch) + self._rot) % len(_CYCLE)]
        return ch

    def forward(self, i: int) -> int | None:
        """Return the ``]`` matching the effective ``[`` at ``i``, if any."""
        depth = 1
        j = i + 1
        while j < len(self._chars):
            ch = self.at(j)
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return None

    def backward(self, i: int) -> int | None:
        """Return the ``[`` matching the effective ``]`` at ``i``, if any."""
        depth = 1
        j = i - 1
        while j >= 0:
            ch = self.at(j)
            if ch == "]":
                depth += 1
            elif ch == "[":
                depth -= 1
                if depth == 0:
                    return j
            j -= 1
        return None


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

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.prog.rotation(),
            tuple(self.tape),
            self.ptr,
            self.ind,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the cursor and rotation."""
        if self.halted:
            return
        prog = self.prog
        char = prog.at(self.ind)
        if char == ">":
            self.ptr += 1
            if self.ptr == len(self.tape):
                self.tape.append(0)
        elif char == "<":
            if self.ptr:
                self.ptr -= 1
        elif char == "+":
            self.tape[self.ptr] = (self.tape[self.ptr] + 1) % 256
        elif char == "-":
            self.tape[self.ptr] = (self.tape[self.ptr] - 1) % 256
        elif char == ".":
            self.io.print_char(chr(self.tape[self.ptr]))
        elif char == ",":
            self.tape[self.ptr] = self.io.input_char()
        elif char == "[" and self.tape[self.ptr] == 0:
            prog.rotate()
            partner = prog.forward(self.ind)
            if partner is None:
                raise HaltError("an executed '[' has no bracket partner")
            self.ind = partner + 1
            return
        elif char == "]" and self.tape[self.ptr] != 0:
            prog.rotate()
            partner = prog.backward(self.ind)
            if partner is None:
                raise HaltError("an executed ']' has no bracket partner")
            self.ind = partner + 1
            return

        prog.rotate()
        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a ROTfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
