"""Executed first-output semantics for the Factor normalization corpus.

The leading-constant count treats prefix-normalized words as descriptions of
behaviours.  This module decodes the proof witnesses, runs them to the first
printed character on every input, and reports how many descriptions share a
behaviour.  A behaviour is the per-input tuple ``("out", char, cursor)``; the
cursor is the input position at that first output, the consumption signature.
"""

from __future__ import annotations

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.brainfuck import _Machine

#: Runs past this many steps on a valid row are undecided, not observed.
_STEP_LIMIT = 200_000


class _FirstOutput(IO):
    """Read a fixed string and stop the run at its first printed character."""

    def __init__(self, stdin: str) -> None:
        super().__init__()
        self._source = stdin
        self._offset = 0
        self.observed = ""

    def _read(self, _prompt: str) -> str:
        raise EOFError

    def _read_char(self, _prompt: str) -> str:
        if self._offset == len(self._source):
            raise EOFError
        char = self._source[self._offset]
        self._offset += 1
        return char

    def _write(self, _value: object) -> None:
        pass

    def print_char(self, char: str) -> None:
        self.observed = char
        raise StopIteration

    def position(self) -> int:
        """Return the input cursor, which later edits must not disturb."""
        return self._offset


def first_output(code: str, bits: str, limit: int = _STEP_LIMIT) -> tuple[object, ...]:
    """Run ``code`` on one input to its first print.

    Returns ``("out", char, cursor)``, or the status ``("bad-brackets",)``,
    ``("exhausted",)``, ``("nonhalting",)``, or ``("halt",)`` when no print
    precedes it.  ``limit`` bounds only the undecided runs.
    """
    io = _FirstOutput(bits)
    try:
        machine = _Machine(code, io)
    except ValueError:
        return ("bad-brackets",)
    steps = 0
    try:
        while not machine.halted:
            if steps >= limit:
                return ("nonhalting",)
            machine.step()
            steps += 1
    except StopIteration:
        return ("out", io.observed, io.position())
    except EOFError:
        return ("exhausted",)
    return ("halt",)


def behaviour(
    code: str, n: int, limit: int = _STEP_LIMIT
) -> tuple[tuple[object, ...], ...]:
    """Return the first-output signature over every ``n``-bit input."""
    return tuple(
        first_output(code, format(row, f"0{n}b"), limit) for row in range(2**n)
    )


def corpus(nmax: int = 3, parity_to: int = 7) -> list[tuple[int, str]]:
    """Return exhaustive tables through ``nmax`` inputs, then parity tables.

    Parity beyond the exhaustive range extends the sample without a search;
    its tables are ``sum of input bits`` modulo two over the ``2**n`` rows.
    """
    tables = [
        (n, format(value, f"0{2**n}b"))
        for n in range(1, nmax + 1)
        for value in range(2 ** (2**n))
    ]
    tables.extend(
        (n, "".join(str(i.bit_count() % 2) for i in range(2**n)))
        for n in range(nmax + 1, parity_to + 1)
    )
    return tables


def delete_pattern(code: str, pattern: str) -> str:
    """Delete every occurrence of ``pattern``, repeating to a fixed point."""
    while pattern in code:
        code = code.replace(pattern, "")
    return code
