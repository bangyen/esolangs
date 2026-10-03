"""Boolean template generator for bio."""

from esolangs.tools.helpers import _ASCII_ZERO, TEMPLATE_CHAR, _validate_truth_table

__all__ = ["BIO_PAIR", "bio"]


BIO_PAIR = ("0oz;", "0ox;")


def bio(truth_table: str) -> str:
    """Return a BIO template for a binary, MSB-first ``2**n`` truth table.

    Four-character setters add one to x or write unused z. Horner doubling
    through y costs eight commands per input and leaves y zero. Starting y
    at table[0], 2**n-1 nested decrement loops telescope adjacent transitions
    (0oy rise, 1oy fall) to y=table[index], printed with 1iy.
    """
    n = _validate_truth_table(truth_table)

    def yop(a: str, b: str) -> str:
        if a == b:
            return ""
        return "0oy;" if a == "0" else "1oy;"

    pack = _BIO_DOUBLE.join([TEMPLATE_CHAR * len(BIO_PAIR[0])] * n)
    # Loop ``j`` wraps ``j + 1``: opens, then closes, joined once (O(2**n)).
    opens = [
        "0ix{1ox;" + yop(truth_table[j - 1], truth_table[j]) for j in range(1, 2**n)
    ]
    init = "0oy;" if truth_table[0] == "1" else ""
    closes = "};" * len(opens)
    return pack + init + "".join(opens) + closes + "0oy;" * _ASCII_ZERO + "1iy;"


#: ``x = 2 * x`` through ``y``: the first loop moves each unit of ``x`` into
#: ``y`` twice, the second moves ``y`` back; both registers stay non-negative,
#: so each loop terminates and ``y`` ends at zero.
_BIO_DOUBLE = "0ix{1ox;0oy;0oy;};0iy{1oy;0ox;};"
