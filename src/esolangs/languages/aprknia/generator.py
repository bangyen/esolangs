"""Aprknia Boolean program generator: a decision tree of positive loops.

Each node reads a byte with selector 0 and keeps its parity, the bit
``b``.  ``[...]`` enters only on ``b = 1`` and leaves -1, so adding 1
leaves 0 on the one arm and 1 on the zero arm; the second loop then runs
the zero arm only.  Leaves print 0 or 1 as an integer with selector 2.
Nothing is ever dropped: loops test only the top, every piece pushes the
values it uses, and the garbage below is never read.

Size:
    O(T) in the tree's nodes; n=4 parity: 586 chars

Decisions:
    Leaves print with selector 2, not 1: the integer 0 or 1 costs at most
    the 9-command build, against building 48 or 49 from ones for a byte.
    Constant spans and ignored inputs read with ``11*,``: the 0 that
    ``11*`` leaves on top is the selector, so no parity is needed.
"""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table, constant_span_test
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: ``11*`` pushes 2, 0, 1, 1, 0.  Its top 0 is a read selector (``_SKIP``);
#: ``!!!`` leaves 2, 0 so ``~*`` after the read is byte mod 2, the bit.
#: ``_MINUS_ONE`` leaves -1 and ``_ADD_ONE`` makes it 0 (the one arm ran) or
#: 0 into 1; ``_EXIT`` is a top 0 that ends a loop.
_SKIP = "11*,"
_READ = "11*!!!,~*"
_MINUS_ONE = "11*1*!!!"
_ADD_ONE = "1*!!!!"
_EXIT = "11*"
_LEAF = {"0": "11*!!!~,", "1": "11*~*!!!,"}


def aprknia(truth_table: str) -> str:
    """Build an Aprknia program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    n = len(truth_table).bit_length() - 1
    constant = constant_span_test(truth_table)

    @cache
    def build(lo: int, hi: int) -> str:
        if constant(lo, hi):
            left = (hi - lo).bit_length() - 1
            return _SKIP * left + _LEAF[truth_table[lo]]
        mid = (lo + hi) // 2
        zero, one = build(lo, mid), build(mid, hi)
        if zero == one:
            return _SKIP + zero
        return (
            _READ + "[" + one + _MINUS_ONE + "]" + _ADD_ONE + "[" + zero + _EXIT + "]"
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
