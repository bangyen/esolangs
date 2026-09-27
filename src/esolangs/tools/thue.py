"""Thue boolean program builder: twenty-one rules that halve one table.

``thue(truth_table)`` puts the whole table in the starting state, one
character per entry, and rewrites it in place: reading a bit replaces each
adjacent *pair* of entries with one of the two, so the state halves per
input and the last character left is the answer.  The rule set is fixed --
twenty-one rules, whatever the arity -- so the emission is ``T + 199``
characters, the smallest per-entry cost in the registry.

Thue draws which rewrite to make, so the rules are written to leave it
nothing to draw: **every state this program reaches has exactly one
applicable rule at exactly one position.**  That is what makes the answer
reproducible without pinning the language's randomness, and it is asserted by
running the programs rather than argued here -- see
``tests/tools/test_boolean_classics.py``.

Two pairs of rules exist only to keep that true.  ``LRaE``/``LRbE`` fire when
one entry is left and print it; the round-start rules spell *two* entries
(``LRaa`` and its three siblings) so that they cannot also match then.  A
single ``LR`` rule would have collided with both print rules, and under a
real draw the run would sometimes start a round that reads an ``n + 1``st
input instead of answering.

The entries are laid out in bit-reversed order.  Adjacent pairs differ in
the *least* significant index bit, but the inputs arrive most significant
first, so position ``p`` holds row ``reverse(p)``: then the first bit read
selects within pairs, the second within pairs of what is left, and so on.
Laying the table out in row order instead would need the first bit to select
a *half*, which no local rewrite can do.

The marker sweeps right selecting (``P`` keeps the first of each pair, ``Q``
the second), turns into ``R`` at the right sentinel, sweeps back to the left
sentinel, and becomes ``M``, which reads the next bit.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table

#: Left and right sentinels, the read marker, the two selecting markers, and
#: the return marker.  Table entries are ``a``/``b`` so that a ``0``/``1``
#: input line cannot be mistaken for one.
_RULES = "\n".join(
    [
        # One entry left: print it and empty the state, which halts.
        "LRaE::=~0",
        "LRbE::=~1",
        # Two or more left: start a round.  Spelled over two entries so
        # neither of the print rules above can match the same state.
        "LRaa::=LMaa",
        "LRab::=LMab",
        "LRba::=LMba",
        "LRbb::=LMbb",
        "M::=:::",
        "0::=P",
        "1::=Q",
        # ``P`` keeps the first of each pair, ``Q`` the second.  The
        # unprocessed suffix is always even, so a marker meets two entries or
        # the sentinel and never one entry alone.
        "Paa::=aP",
        "Pab::=aP",
        "Pba::=bP",
        "Pbb::=bP",
        "PE::=RE",
        "Qaa::=aQ",
        "Qab::=bQ",
        "Qba::=aQ",
        "Qbb::=bQ",
        "QE::=RE",
        # Carry the marker back to the left sentinel for the next round.
        "aR::=Ra",
        "bR::=Rb",
        "::=",
    ]
)


def thue(truth_table: str) -> str:
    """Return a Thue program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    _validate_truth_table(truth_table)
    length = len(truth_table)
    # Position p holds row reverse(p): the halving selects on the low index
    # bit, and the inputs arrive high bit first.  ``row`` is carried as a
    # bit-reversed counter -- carry from the top bit down -- rather than
    # reversed per position, which would cost an O(log T) factor.
    entries = []
    row = 0
    for _position in range(length):
        entries.append("ab"[truth_table[row] == "1"])
        carry = length >> 1
        while row & carry:
            row ^= carry
            carry >>= 1
        row |= carry
    return f"{_RULES}\nLM{''.join(entries)}E"
