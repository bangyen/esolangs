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
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_ROTATION = str.maketrans("+-><,.[]", "-><,.[]+")


def _rotate(prog: list[str]) -> None:
    """Advance every command in ``prog`` one step along the cycle."""
    for i, ch in enumerate(prog):
        if ch in "+-><,.[]":
            prog[i] = ch.translate(_ROTATION)


def _forward(prog: list[str], i: int) -> int | None:
    """Return the index of the ``]`` matching the ``[`` at ``i``.

    Seeks forward from ``i + 1`` in ``prog``, so the bracket that fired
    (which has rotated to ``]`` at ``i``) is not counted.
    """
    depth = 1
    j = i + 1
    while j < len(prog):
        if prog[j] == "[":
            depth += 1
        elif prog[j] == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return None


def _backward(prog: list[str], i: int) -> int | None:
    """Return the index of the ``[`` matching the ``]`` at ``i``.

    Seeks backward from ``i - 1`` in ``prog``; the fired ``]`` has rotated
    away at ``i``, so it is not counted.
    """
    depth = 1
    j = i - 1
    while j >= 0:
        if prog[j] == "]":
            depth += 1
        elif prog[j] == "[":
            depth -= 1
            if depth == 0:
                return j
        j -= 1
    return None


def run(code: str, io: IO) -> None:
    """Run a ROTfuck program."""
    prog = list(code)
    tape: list[int] = [0]
    ptr = ind = 0

    while ind < len(prog):
        char = prog[ind]
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
            _rotate(prog)
            partner = _forward(prog, ind)
            if partner is None:
                raise HaltError("an executed '[' has no bracket partner")
            ind = partner + 1
            continue
        elif char == "]" and tape[ptr] != 0:
            _rotate(prog)
            partner = _backward(prog, ind)
            if partner is None:
                raise HaltError("an executed ']' has no bracket partner")
            ind = partner + 1
            continue

        _rotate(prog)
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
