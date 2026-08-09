"""Interpreter for Brainfuck.

The semantics deliberately match the ASCII-art interpreter (which is
brainfuck with an art alphabet) so that the two are interchangeable: an
8-bit wrapping tape, rightward growth, ``<`` clamped at the left edge, and
matching-bracket loops.  This is what lets the BF-to-ASCII-art transpiler
be verified end-to-end.

The brainfuck spec defines ``[``/``]`` only for matched pairs; a program
with unbalanced brackets is malformed, so the interpreter rejects it with a
:class:`ValueError` rather than inventing a halt the language does not
specify.
"""

import sys

from esolangs.interpreters.io import IO


def matches(code: str) -> dict[int, int]:
    """Map each bracket to its partner, ``{open: close, close: open}``.

    Raises :class:`ValueError` if the brackets are unbalanced: the spec
    defines ``[``/``]`` only for matched pairs.
    """
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, char in enumerate(code):
        if char == "[":
            stack.append(i)
        elif char == "]":
            if not stack:
                raise ValueError(f"unmatched ']' at position {i}")
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    if stack:
        raise ValueError(f"unmatched '[' at position {stack[-1]}")
    return res


def run(code: str, io: IO) -> None:
    """Run a Brainfuck program."""
    tape: list[int] = [0]
    m = matches(code)

    ind = ptr = 0

    while ind < len(code):
        char = code[ind]
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
            ind = m[ind]

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
