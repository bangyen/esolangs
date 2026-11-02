"""Independent one-data-row nibbles and the retained general lookup layouts."""

from typing import Literal

from esolangs.generation.helpers import _validate_truth_table, input_weights
from esolangs.languages.befunge.generator import (
    _check_cap,
    _constant,
    _natural_befunge,
    _packed_befunge,
    _plain_befunge,
    _wins,
)


def ablate(table: str, rule: Literal["default", "one_row_nibbles"]) -> str:
    """Return the default lookup or disable its one-data-row construction."""
    n = _validate_truth_table(table)
    _check_cap(n)
    if len(set(table)) == 1:
        return _constant(n, table[0], None)
    weights, values = input_weights(table, n)
    if len(values) <= 2:
        return _natural_befunge(table)
    if rule == "default" and len(values) <= 4 * 80:
        parts = []
        rank = 0
        for weight in weights:
            if not weight:
                parts.append("&$")
                continue
            parts.append(
                "&1+"
                if rank == 0
                else "&3*1+*"
                if rank == 1
                else "&"
                if rank == 2
                else "2*&+"
            )
            rank += 1
        if rank == 2:
            parts.append("0")
        count = len(values) // 4
        data = "".join(
            chr(
                32
                + sum(
                    int(values[((s & 1) * 2 + (s >> 1)) * count + i]) << s
                    for s in range(4)
                )
            )
            for i in range(count)
        )
        return "".join(parts) + "1g48*-\\/2%.@\n" + data
    reads = "".join("&\\2*+" if weight else "&$" for weight in weights)
    if len(values) > 1 << 10:
        return _packed_befunge(values, reads, None)
    plain = _plain_befunge(values, reads, None)
    packed = _packed_befunge(values, reads, None)
    return packed if _wins(packed, plain) else plain
