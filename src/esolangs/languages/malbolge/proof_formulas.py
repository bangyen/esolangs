"""Executed command and snapshot-bit bounds."""

from esolangs.languages.malbolge.interpreter import _op


def execution(n: int, program: str) -> int:
    """The worst row: the straight-line main code, then the longest reachable stub.

    Main code runs from cell 0 through its closing ``i`` and depends on n only.
    A row then runs one stub, in full: ``0`` and ``x`` three commands, ``1`` and
    ``n`` four plus the span from landing to last operand, whose two hubs each
    give ``1``: 195, 179 and ``n``: 199, 190.  The 199 hub is reached from n = 3
    (``1``'s 195 is the longest below).
    """
    end = next(a for a, char in enumerate(program) if _op(ord(char), a) == "i")
    return end + 1 + (199 if n >= 3 else 195)


def workspace(n: int, program: str) -> int:
    """The source's bits, 10 bits per step, three registers, halt flag, input count.

    Every cell starts printable (6 or 7 bits: the build fills the store).  A step
    re-enciphers the cell at c (stays 33..126: +1 bit at most) and `*`/`p` writes
    the cell at d (<= 59048: 16 bits, +10 at most); a cell grows once per
    visit but is bounded by its first write, so the total growth is <= 10 per step.
    """
    bits = sum(len(bin(ord(c))) - 2 for c in program if not c.isspace())
    return bits + 10 * execution(n, program) + 49 + n.bit_length()
