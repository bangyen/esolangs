"""Thue boolean program builder: nineteen rules that halve one table.

The table is the starting state, one character an entry; reading a bit
replaces each adjacent *pair* with one of the two, so the state halves per
input and the last character is the answer, for ``T + 187`` characters.
Entries are bit-reversed: pairs differ in the *least* significant index bit,
inputs arrive most significant first, and no rewrite can select a half.

Thue draws which rewrite to make; these rules leave nothing to draw (every
state reached has one rule at one position), so the answer is reproducible
unpinned, as the classics tests assert to ``n = 3`` under several draws.
"""

from __future__ import annotations

from string import ascii_letters

from esolangs.tools.helpers import _validate_truth_table

#: Entries are ``a``/``b`` so a ``0``/``1`` input line is never mistaken for
#: one; ``L``/``E`` are sentinels, ``M``/``R`` and the read ``0``/``1`` markers.
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
        # The line read is the marker: ``0`` keeps the first of each pair, ``1``
        # the second; the suffix left stays even, so none meets one entry.
        "0aa::=a0",
        "0ab::=a0",
        "0ba::=b0",
        "0bb::=b0",
        "0E::=RE",
        "1aa::=a1",
        "1ab::=b1",
        "1ba::=a1",
        "1bb::=b1",
        "1E::=RE",
        # Carry the marker back to the left sentinel for the next round.
        "aR::=Ra",
        "bR::=Rb",
        "::=",
    ]
)


def _chunk_marker(index: int, digits: int) -> str:
    """Return a fixed-width name containing no table or control symbol."""
    alphabet = "".join(char for char in ascii_letters if char not in "abLMRECD")
    name = []
    for _ in range(digits):
        index, digit = divmod(index, len(alphabet))
        name.append(alphabet[digit])
    return "".join(reversed(name))


def thue(truth_table: str, width: int | None = None) -> str:
    """Return a Thue program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit. Narrow layouts expand named chunks before reading.
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
    table = "".join(entries)
    program = f"{_RULES}\nLM{table}E"
    if width is None or width <= 0 or max(map(len, program.splitlines())) <= width:
        return program
    # Contract only a completed return sweep. D restores L before reading,
    # so the shorter start rules cannot fire on R in the table's interior.
    rules_text = _RULES.replace("LR", "C").replace("::=LM", "::=D")
    rules_text = rules_text.removesuffix("::=") + "LR::=C\nD::=LM\n::="
    narrow = f"{rules_text}\nLM{table}E"
    if max(map(len, narrow.splitlines())) <= max(width, 9):
        return narrow
    digits, capacity = 1, len(ascii_letters) - len("abLMRECD")
    while capacity < length:
        digits += 1
        capacity *= len(ascii_letters) - len("abLMRECD")
    marker_width = digits
    # Payload covers its names' overhead, keeping even the narrowest source O(T).
    payload = max(marker_width, width - marker_width - max(marker_width, 2) - 3)
    rules = rules_text.splitlines()[:-1]
    for index, offset in enumerate(range(0, length, payload)):
        marker = _chunk_marker(index, digits)
        following = (
            _chunk_marker(index + 1, digits) if offset + payload < length else "RE"
        )
        rules.append(f"{marker}::={table[offset : offset + payload]}{following}")
    # No input marker exists until expansion finishes and R sweeps back to L.
    expanded = "\n".join([*rules, "::=", "L" + _chunk_marker(0, digits)])
    if max(map(len, expanded.splitlines())) >= max(map(len, program.splitlines())):
        return program
    return expanded
