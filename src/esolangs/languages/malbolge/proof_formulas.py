"""Executed command and snapshot-bit bounds."""

from esolangs.languages.malbolge.generator.digits import _SHORT_N
from esolangs.languages.malbolge.interpreter import _initial_memory, _op


def _stub(n: int) -> int:
    """The longest stub's commands: one hub per label to n = 13, else two."""
    return 197 if n <= _SHORT_N else 199


def execution(n: int, program: str) -> int:
    """The worst row: the straight-line main code, then the longest reachable stub.

    Main code runs from cell 0 through its closing ``i`` and depends on n only.
    A row then runs one stub, in full: ``0`` and ``x`` three commands, ``1`` and
    ``n`` four plus the span from landing to last operand.  The short layout
    (n <= 13) has one hub each, the longest 197; the full one has two each, the
    longest 199.
    """
    end = next(a for a, char in enumerate(program) if _op(ord(char), a) == "i")
    return end + 1 + _stub(n)


def workspace(n: int, program: str) -> int:
    """Memory bits, a bit a step, ten a `*`/`p` write, registers, flag, input count.

    The memory is the source's cells then the fill past a short source.

    Main code runs each cell once, so its writes are those before the closing
    ``i``; a stub runs at most 197 or 199 steps, each at most one write.
    """
    bits = sum(word.bit_length() for word in _initial_memory(program))
    end = next(a for a, char in enumerate(program) if _op(ord(char), a) == "i")
    writes = sum(
        1 for a, c in enumerate(program[: end + 1]) if _op(ord(c), a) in ("*", "p")
    )
    return bits + execution(n, program) + 10 * (writes + _stub(n)) + 49 + n.bit_length()
