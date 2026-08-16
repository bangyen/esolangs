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


def run(code: str, io: IO) -> None:
    """Run a ROTfuck program."""
    prog = _Program(code)
    tape: list[int] = [0]
    ptr = ind = 0

    while ind < len(code):
        char = prog.at(ind)
        if char == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif char == "<":
            if ptr:
                ptr -= 1
        elif char == "+":
            tape[ptr] = (tape[ptr] + 1) % 256
        elif char == "-":
            tape[ptr] = (tape[ptr] - 1) % 256
        elif char == ".":
            io.print_char(chr(tape[ptr]))
        elif char == ",":
            tape[ptr] = io.input_char()
        elif char == "[" and tape[ptr] == 0:
            prog.rotate()
            partner = prog.forward(ind)
            if partner is None:
                raise HaltError("an executed '[' has no bracket partner")
            ind = partner + 1
            continue
        elif char == "]" and tape[ptr] != 0:
            prog.rotate()
            partner = prog.backward(ind)
            if partner is None:
                raise HaltError("an executed ']' has no bracket partner")
            ind = partner + 1
            continue

        prog.rotate()
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
