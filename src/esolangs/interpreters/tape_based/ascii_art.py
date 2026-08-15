"""Interpreter for ASCII art (brainfuck with an art alphabet).

Art blocks decode to the eight brainfuck commands plus . / , / < / > / + / [
and ].  The tape, clamping, wrapping, and bracket semantics are those of the
plain brainfuck interpreter, so the two are interchangeable; execution is
delegated to ``brainfuck.run`` after decoding.

Exhausted input raises :class:`EOFError` (the repo-wide
convention); malformed programs raise :class:`ValueError`.
"""

import re
import sys

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.brainfuck import run as run_bf


def parse(code: str) -> str:
    """Decode ASCII-art blocks into their brainfuck command characters."""
    if not code:
        return ""
    code = re.sub(" +\n", "\n", code)
    blocks = code.split("\n\n")
    res = ""
    sym = {
        (0, "-"): "-",
        (1, "#"): ".",
        (2, "|"): ",",
        (3, "\\"): "<",
        (3, "/"): ">",
        (4, "|"): "+",
        (5, "_"): "[",
        (5, "|"): "]",
    }

    for c in blocks:
        if not c:
            raise ValueError("ASCII-art program has an empty block")
        t = (c.count("\n"), c[-1])
        if t in sym:
            res += sym[t]
    return res


def run(code: str, io: IO) -> None:
    """Run an ASCII-art program after decoding it to brainfuck."""
    run_bf(parse(code), io)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
