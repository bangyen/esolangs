"""Boolean template generator for bio."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    TEMPLATE_CHAR,
    _validate_truth_table,
    input_weights,
)
from esolangs.tools.wrap import _bio as _wrap_bio

__all__ = ["BIO_PAIR", "bio"]


BIO_PAIR = ("0oz;", "0ox;")


def bio(truth_table: str) -> str:
    """Return a BIO template for a binary, MSB-first ``2**n`` truth table.

    Four-character setters add one to x or write unused z. Horner doubling
    through y costs eight commands per input and leaves y zero. Starting y
    at table[0], 2**n-1 nested decrement loops telescope adjacent transitions
    (0oy rise, 1oy fall) to y=table[index], printed with 1iy.  An ignored
    input's setter runs with x parked in y and is then cleared
    (:data:`_BIO_SKIP`), so the table indexes the rest.  A guard keeping the
    shorter of full and projected saved 0.0% at n=4-7 (constants at n<=2 are
    the only tables projection lengthens, by 28 characters) and was retired;
    telescoping saves 39.6% at n=7 over resetting y per row.  Each row is one
    nested loop that sets where the walk stops, so no row is dropped; loops
    nest and none is called, so none is shared.  A trailing flat run is one level.
    """
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)
    return _bio(table, weights)


def _bio(truth_table: str, weights: list[int]) -> str:
    """Return the template indexing ``truth_table`` by the weighted inputs."""
    n = len(truth_table).bit_length() - 1

    def yop(a: str, b: str) -> str:
        if a == b:
            return ""
        return "0oy;" if a == "0" else "1oy;"

    setter = TEMPLATE_CHAR * len(BIO_PAIR[0])
    pack, read = "", False
    for weight in weights:
        if weight:
            pack += (_BIO_DOUBLE if read else "") + setter
            read = True
        else:
            pack += _BIO_SKIP[0] + setter + _BIO_SKIP[1]
    ops = [yop(truth_table[j - 1], truth_table[j]) for j in range(1, 2**n)]
    while len(ops) > 1 and not ops[-1] and not ops[-2]:
        ops.pop()
    # Loop ``j`` wraps ``j + 1``: opens, then closes, joined once (O(2**n)).
    opens = ["0ix{1ox;" + op for op in ops]
    init = "0oy;" if truth_table[0] == "1" else ""
    closes = "};" * len(opens)
    return pack + init + "".join(opens) + closes + "0oy;" * _ASCII_ZERO + "1iy;"


#: ``x = 2 * x`` through ``y``: the first loop moves each unit of ``x`` into
#: ``y`` twice, the second moves ``y`` back; both registers stay non-negative,
#: so each loop terminates and ``y`` ends at zero.
_BIO_DOUBLE = "0ix{1ox;0oy;0oy;};0iy{1oy;0ox;};"

#: Around an ignored input's setter: park ``x`` in ``y``, then clear what the
#: setter added and move ``x`` back, so ``y`` ends at zero as doubling leaves it.
_BIO_SKIP = ("0ix{1ox;0oy;};", "0ix{1ox;};0iy{1oy;0ox;};")


LANGUAGE = Language(
    "BIO",
    "register_based.bio",
    boolean=bio,
    contract=BooleanContract(),
    wrap=_wrap_bio,
    example=Example(pair=BIO_PAIR),
)
