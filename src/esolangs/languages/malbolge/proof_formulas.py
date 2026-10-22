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
    """Source bits, a bit a step, ten a `*`/`p` write, registers, flag, input count.

    Main code runs each cell once, so its writes are those before the closing
    ``i``; a stub runs at most 199 steps, each at most one write.
    """
    bits = sum(len(bin(ord(c))) - 2 for c in program if not c.isspace())
    end = next(a for a, char in enumerate(program) if _op(ord(char), a) == "i")
    writes = sum(
        1 for a, c in enumerate(program[: end + 1]) if _op(ord(c), a) in ("*", "p")
    )
    return bits + execution(n, program) + 10 * (writes + 199) + 49 + n.bit_length()
