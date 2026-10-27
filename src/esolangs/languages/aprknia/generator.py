"""Aprknia Boolean program generator: a decision tree of positive loops.

Each node reads a byte with selector 0 and keeps its parity, the bit
``b``.  ``[!O<-1>]`` enters only on ``b = 1`` and leaves -1, so adding 1
leaves 0 on the one arm and 1 on the zero arm; ``[!Z<0>]!`` then runs the
zero arm and drops the 0 either way.  Leaves push the answer and print it
as an integer with selector 2, then drop it, so every subtree is
stack-neutral.

Size:
    O(T) in the tree's nodes; n=4 parity: 1131 chars

Decisions:
    Leaves print with selector 2, not 1: the integer 0 or 1 costs at most
    the 8-command zero, against building 48 or 49 from ones for a byte.
"""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table, constant_span_test
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Constants from the page's snippets: ``*!!!~!`` is b-a, ``*!!!!`` b+a.
_ZERO = "11*!!!~!"
_TWO = "11*!!!!"
_MINUS_ONE = _ZERO + "1*!!!~!"
#: Reads a byte and keeps its parity, the bit: ``*~!~!~!~!`` is b mod a.
_READ = _ZERO + "," + _TWO + "*~!~!~!~!"
_LEAF = {"0": _ZERO + _TWO + ",!", "1": "1" + _TWO + ",!"}


def aprknia(truth_table: str) -> str:
    """Build an Aprknia program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    n = len(truth_table).bit_length() - 1
    constant = constant_span_test(truth_table)

    @cache
    def build(lo: int, hi: int) -> str:
        if constant(lo, hi):
            left = (hi - lo).bit_length() - 1
            return (_READ + "!") * left + _LEAF[truth_table[lo]]
        mid = (lo + hi) // 2
        zero, one = build(lo, mid), build(mid, hi)
        if zero == one:
            return _READ + "!" + zero
        add_one = "1*!!!!"
        return (
            _READ
            + "[!"
            + one
            + _MINUS_ONE
            + "]"
            + add_one
            + ("[!" + zero + _ZERO + "]!")
        )

    return build(0, 2**n)


LANGUAGE = Language(
    "Aprknia",
    "aprknia",
    category="stack_based",
    boolean=aprknia,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=wrap_chars,
)
