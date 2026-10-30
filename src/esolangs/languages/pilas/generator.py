"""Pilas Boolean program generator: a decision tree on line one.

Line two idles in ``0{0}``, a loop that never exits, so only line one's
pointer can end the run.  Each node reads a byte, subtracts 48 to get the
bit ``b`` and runs ``:{Z+2+1}1-:{O+1+1}1-``: the first ``{`` enters only
on ``b = 0`` and leaves a 2 behind, the second only on the one arm.  Every
subtree pushes exactly one 0, so ``+`` folds it into the flag below and
each node, like each leaf, leaves one 0 for its parent.  A span whose
halves are opposite constants prints its first input's byte, or 97 minus it.

Size:
    O(T) in the tree's nodes; n=4 parity: 266 chars

Decisions:
    Residues fold with ``+``, not ``~``: a moved value would land on line
    two's stack, where its ``{`` would pop it instead of its own 0.
"""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table, constant_span_test
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Pushes 48, the byte ``'0'``.
_ZERO_BYTE = "6:+:+:+"
#: Reads one input byte as its bit.
_READ = "," + _ZERO_BYTE + "-"
#: Reads one input byte and leaves a 0 for it, skipping the 48.
_DROP = ",:-"
#: Pushes 97 = 48 + 49, so ``97 - byte`` is the other bit's byte.
_NINETY_SEVEN = _ZERO_BYTE + ":+1+"


def pilas(truth_table: str) -> str:
    """Build a Pilas program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    n = len(truth_table).bit_length() - 1
    constant = constant_span_test(truth_table)

    @cache
    def build(lo: int, hi: int) -> str:
        if constant(lo, hi):
            left = (hi - lo).bit_length() - 1
            bump = "1+" if truth_table[lo] == "1" else ""
            return _DROP * left + _ZERO_BYTE + bump + ".0" + "+" * left
        mid = (lo + hi) // 2
        if constant(lo, mid) and constant(mid, hi):
            # The first input is the answer: print its byte, or 97 minus it,
            # then read the rest away.  See [ablations.input_literal].
            rest = (hi - lo).bit_length() - 2
            head = "," if truth_table[lo] == "0" else _NINETY_SEVEN + ",-"
            return head + "." + (_DROP * rest + "+" * (rest - 1) if rest else "0")
        zero, one = build(lo, mid), build(mid, hi)
        if zero == one:
            # An ignored input is still read, then zeroed and folded away.
            return _DROP + zero + "+"
        return _READ + ":{" + zero + "+2+1}1-:{" + one + "+1+1}1-"

    return build(0, 2**n) + "\n0{0}"


LANGUAGE = Language(
    "Pilas",
    "pilas",
    category="stack_based",
    boolean=pilas,
    contract=BooleanContract(input_shape="char_stream"),
    no_wrap="a newline starts line two, which runs a different stack",
)
