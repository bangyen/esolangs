"""Thue boolean program builder: twenty-one rules that halve one table.

The table is the starting state, one character an entry; reading a bit
replaces each adjacent *pair* with one of the two, so the state halves per
input and the last character is the answer, for ``T + 199`` characters.
Entries are bit-reversed: pairs differ in the *least* significant index bit,
inputs arrive most significant first, and no rewrite can select a half.

Thue draws which rewrite to make, and these rules leave nothing to draw:
every state reached has one applicable rule at one position, which makes the
answer reproducible without pinning the language's randomness.  Asserted to
``n = 3`` under three seeds and the unseeded draw, in the classics tests.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table

#: Entries are ``a``/``b`` so a ``0``/``1`` input line is never mistaken for
#: one; ``L``/``E`` are sentinels and ``M``/``P``/``Q``/``R`` the markers.
_RULES = "\n".join(
    [
        # One entry left: print it and empty the state, which halts.
        "LRaE::=~0",
        "LRbE::=~1",
        # Start a round, over two entries so neither print rule above can also
        # match: one ``LR`` rule collided, and a draw then read an n+1st input.
        "LRaa::=LMaa",
        "LRab::=LMab",
        "LRba::=LMba",
        "LRbb::=LMbb",
        "M::=:::",
        "0::=P",
        "1::=Q",
        # ``P`` keeps the first of each pair and ``Q`` the second; the
        # unprocessed suffix stays even, so a marker never meets one entry.
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
    # A bit-reversed counter: reversing per position would cost an O(log T).
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
