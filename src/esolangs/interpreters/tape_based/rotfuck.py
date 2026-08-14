"""Interpreter for ROTfuck.

Brainfuck whose program text rotates: every executed command advances all
non-comment characters one step along the cyclic alphabet ``+-><,.[]``
(``+`` becomes ``-``, ``-`` becomes ``>``, ..., ``]`` becomes ``+``).  The
command at the instruction pointer is therefore a function of how many
commands have run, not just of the source text.

The tape follows the same conventions as the plain Brainfuck interpreter in
this package: an 8-bit wrapping tape that grows to the right, ``<`` clamped
at the left edge, and :class:`EOFError` when ``,`` runs out of input.

Bracket partners are computed once from the source with the standard
stack-based algorithm, as in Brainfuck.  The rotation does not change
positions, only the character stored at each position, so the partners stay
fixed; the difference from Brainfuck is that a source whose brackets are
unbalanced is *not* malformed, because the rotation can bring any character
(including a ``[`` or ``]``) to the pointer at any time.  A bracket that is
executed without a partner is therefore a runtime error, not a load error,
and the interpreter halts with :class:`~esolangs.exceptions.HaltError`.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_ROTATION = str.maketrans("+-><,.[]", "-><,.[]+")
_COMMANDS = "+-><,.[]"


def _matches(code: str) -> dict[int, int]:
    """Map each bracket to its partner, ``{open: close, close: open}``.

    Brackets without a partner are simply left out (the rotation makes
    unbalanced sources legal), so a partnerless bracket only fails when it
    is actually executed.
    """
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, char in enumerate(code):
        if char == "[":
            stack.append(i)
        elif char == "]":
            if not stack:
                continue
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    return res


def run(code: str, io: IO) -> None:
    """Run a ROTfuck program."""
    prog = list(code)
    m = _matches(code)
    tape: list[int] = [0]
    ptr = ind = 0

    while ind < len(prog):
        char = prog[ind]
        if char == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif char == "<" and ptr:
            ptr -= 1
        elif char == "+":
            tape[ptr] = (tape[ptr] + 1) % 256
        elif char == "-":
            tape[ptr] = (tape[ptr] - 1) % 256
        elif char == ".":
            io.print_char(chr(tape[ptr]))
        elif char == ",":
            tape[ptr] = io.input_char()
        elif (char == "[" and tape[ptr] == 0) or (char == "]" and tape[ptr] != 0):
            partner = m.get(ind)
            if partner is None:
                raise HaltError(f"an executed '{char}' has no bracket partner")
            ind = partner

        for i, ch in enumerate(prog):
            if ch in _COMMANDS:
                prog[i] = ch.translate(_ROTATION)
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
