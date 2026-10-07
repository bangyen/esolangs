"""Smu Boolean generator: a decision tree of runs, one input bit per run.

A node ``(c0)(c1)n`` stores its halves under the input bit's own names,
``(+)=(|)=``, and ``()+`` pushes the value of the variable the bit names,
the half to run next.  Bytes arrive low bit first, so the input's value is
the first bit of its byte; seven skip programs ``k`` pushed above the half
drop the byte's other bits, one run each, and ``()`` is the node's own
(empty) output.  A leaf ``z``/``o`` drops its bit and outputs the eight bits
of ``'0'``/``'1'``.  A constant subtree folds to a leaf wrapped in one pad
``(X)m`` per skipped level: ``m`` stores X under both bit names, so every
table reads all its bytes.  Source: 5 characters a node, 3 a pad.
"""

from esolangs.tools.helpers import _validate_truth_table, constant_span_test

#: ``k`` drops a run's bit and outputs nothing; ``n`` is a node less its
#: halves, ``m`` a pad; ``z``/``o`` print ``'0'`` (0x30), ``'1'`` (0x31) low bit first.
_MACROS = (
    "k((())=())k"
    "n(+)=(|)=()+kkkkkkk()n"
    "m(+)=(+)()+(|)=()+kkkkkkk()m"
    "z(())=(||||++||)z"
    "o(())=(+|||++||)o"
)


def smu(truth_table: str) -> str:
    """Return a Smu program printing ``truth_table``'s row for its input bytes."""
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)
    parts = [_MACROS]

    def walk(level: int, lo: int, hi: int) -> None:
        if level == n or constant(lo, hi):
            pads = n - level
            parts.append("(" * pads + "zo"[truth_table[lo] == "1"] + ")m" * pads)
            return
        mid = (lo + hi) // 2
        parts.append("(")
        walk(level + 1, lo, mid)
        parts.append(")(")
        walk(level + 1, mid, hi)
        parts.append(")n")

    walk(0, 0, 1 << n)
    return "".join(parts)
