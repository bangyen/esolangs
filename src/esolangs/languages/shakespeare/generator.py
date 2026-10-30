"""Shakespeare Boolean program generator: the table is one number, shifted by the row.

Hamlet is packed with the table as a binary number whose bit ``r`` is
``table[r]``, by Horner's rule in sentences of 64 bits: a zero bit is
``twice``, a one bit ``the sum of twice ... and joy``.  Romeo then reads each
input into Juliet and multiplies himself by ``1 + bit * (2**w - 1)``, where
``w`` is that input's weight and ``2**w`` is ``w`` as a power of two reached
by squaring ``2`` (``the square of`` nested ``log2 w`` times).  Romeo ends as
``2**row``; ``Hamlet / Romeo`` taken mod 2 is the answer.  A table with more
ones than zeros packs its complement and subtracts from 1.  The play is one
line of single-spaced words, so the squarest layout is a plain re-wrap.

Size:
    at most ``16 * T`` characters for ``T = 2**m`` rows of the essential inputs
    plus ``O(m**2)`` for the readers, so linear in T; n=4 parity: 1,226 chars

Decisions:
    * A stack of ``Remember`` sentences, one per row, was not built: reading
      it pops once per row, Theta(T) steps against 2n + 7 here.
"""

from __future__ import annotations

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.registry._language import Language, Shape

#: Bits packed by one sentence; bounds the parser's nesting.
_CHUNK = 64
_TWO = "old joy"
_HEAD = (
    "Table. Romeo, a man. Juliet, a woman. Hamlet, a prince. "
    "Act I: Reading. Scene I: Reading."
)
_READ = "Romeo: Listen to your heart."


def _pack(bits: str) -> str:
    """Return the sentences setting Hamlet to the binary number ``bits``.

    ``bits`` starts with ``1``.  Romeo speaks, so ``yourself`` is Hamlet.
    """
    sentences = []
    acc = "joy"
    rest = bits[1:]
    for start in range(0, len(rest), _CHUNK):
        for bit in rest[start : start + _CHUNK]:
            acc = f"the sum of twice {acc} and joy" if bit == "1" else f"twice {acc}"
        sentences.append(f"You are {acc}.")
        acc = "yourself"
    return " ".join(sentences) if rest else "You are joy."


def _power(exponent: int) -> str:
    """Return ``2 ** (2 ** exponent)`` as nested squares of two."""
    return "the square of " * exponent + _TWO


def _factor(exponent: int) -> str:
    """Return ``1 + bit * (2 ** 2 ** exponent - 1)`` with Juliet holding the bit."""
    return (
        "the sum of joy and the product of me and the difference between "
        f"{_power(exponent)} and joy"
    )


def _program(table: str, n: int, essential: list[int], *, invert: bool) -> str:
    """Return the play for the reduced ``table`` over ``essential`` inputs."""
    m = len(essential)
    stored = "".join("1" if c == ("0" if invert else "1") else "0" for c in table)
    bits = bin(int(stored[::-1], 2))[2:]
    parts = [
        _HEAD,
        "[Enter Romeo and Hamlet]",
        "Romeo:",
        _pack(bits),
        "[Exit Hamlet] [Enter Juliet]",
        "Juliet: You are joy.",
    ]
    for position in range(n):
        parts.append(_READ)
        if position in essential:
            exponent = m - 1 - essential.index(position)
            parts.append(
                f"Juliet: You are the product of yourself and {_factor(exponent)}."
            )
    bit = (
        "the remainder of the quotient between "
        f"the quotient between Hamlet and yourself and {_TWO}"
    )
    if invert:
        bit = f"the difference between joy and {bit}"
    parts.append(f"Juliet: You are {bit}.")
    parts.append("Open your heart.")
    return " ".join(parts)


def shakespeare(truth_table: str) -> str:
    """Build a Shakespeare program printing ``truth_table[row]`` for the inputs.

    A constant table reads every input into Juliet and prints its bit.
    """
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    if not essential:
        reads = " ".join([_READ] * n)
        return (
            f"{_HEAD} [Enter Romeo and Juliet] {reads} "
            f"Romeo: You are {'joy' if truth_table[0] == '1' else 'nothing'}. "
            "Open your heart."
        )
    table = read_at(truth_table, essential, n)
    # A rule, not a race: see [ablations.polarity].
    return _program(table, n, essential, invert=2 * table.count("1") > len(table))


LANGUAGE = Language(
    "Shakespeare",
    "shakespeare",
    category="stack_based",
    boolean=shakespeare,
    shape=Shape.LOOKUP,
    wrap=wrap_space_delimited,
    empty_program="Shakespeare line 1: empty play",
)
