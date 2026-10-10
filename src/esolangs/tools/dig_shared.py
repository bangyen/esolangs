"""Shared Dig lookup bodies selected by an arithmetic prefix index."""

from esolangs.tools.dig_layout import _dig_alt_clear
from esolangs.tools.dig_leaf import _dig_adder, _dig_flat_leaf, _dig_flat_walk, _render


def _dig_indexed_shared(table: str, n: int) -> str | None:
    """Decode two to six prefix bits into shared six-input leaf classes.

    Prefix literals become inert after the selected class is read. Its
    class number adds eight rows to the final six-input lookup per class.
    Entry and stamp legs are charged against the unchanged command ledger.
    """
    bits = n - 6
    if bits not in (2, 3, 4, 5, 6):
        return None
    blocks = [table[i : i + 64] for i in range(0, len(table), 64)]
    unique = list(dict.fromkeys(blocks))
    if not 2 <= len(unique) <= 10:
        return None
    indices = {block: str(i) for i, block in enumerate(unique)}
    prefix = "".join(indices[block] for block in blocks)
    if bits > 4:
        high_bits = bits - bits // 2
        high = [1 << i for i in reversed(range(high_bits))]
        low = [1 << i for i in reversed(range(bits // 2))]
        chars, turns, reads, _exit, box = _dig_flat_leaf(prefix, high, low)
        output = next(p for p, char in chars.items() if char == ":")
        halt = next(p for p, char in chars.items() if char == "@")
        chars[output] = " "
        turns[halt] = 1
        del chars[halt]
        prefix_cost = _dig_flat_walk(high, low)
        exit_row = halt[0]
        offset = 1
        row_offset = 2 - box[2]
        end = halt[1]
        top = box[3] + row_offset + 3
    else:
        chars, turns, reads, exit_at, _box = _dig_adder(
            [1 << i for i in reversed(range(bits))], 1
        )
        if bits == 4:
            # The third product begins a second window; both counts fit one digit.
            cut = 8

            def shift(point: tuple[int, int]) -> tuple[int, int]:
                return point[0], point[1] + int(point[1] >= cut)

            chars = {shift(p): c for p, c in chars.items()}
            turns = {shift(p): h for p, h in turns.items()}
            reads = [
                (shift(at), shift(want), frozenset(shift(p) for p in pending))
                for at, want, pending in reads
            ]
            chars[-1, 0], chars[0, cut], chars[-1, cut] = "7", "$", "4"
            hold = max(c for (r, c), char in chars.items() if r == 1 and char == "$")
            chars[0, hold] = str(hold - exit_at[1] - 1)
            reads.append(((0, cut), (-1, cut), frozenset()))
        end = exit_at[1]
        turns[1, end] = 1
        chars[2, end], chars[2, end - 1] = "$", "1"
        chars[3, end], chars[4, end] = ";", "$"
        reads.extend(
            (
                ((2, end), (2, end - 1), frozenset({(3, end)})),
                ((4, end), (3, end), frozenset()),
            )
        )
        chars.update({(row, end): char for row, char in enumerate(prefix, 5)})
        hold = max(c for (r, c), char in chars.items() if r == 1 and char == "$")
        prefix_cost = 2 * hold + 4 - end
        exit_row = 1
        offset, row_offset = 1, 1
        top = len(prefix) + 8
    merge = 11
    # Entry, decoder, descent, east/down/west connection, shared body.
    rows = 8
    body_cost = (
        _dig_flat_walk([4, 2, 1], [4, 2, 1])
        - ((rows + 14) // 2 - 1)
        + 9
        + 3 * rows * (len(unique) - 1)
    )
    cost = (
        row_offset
        + offset
        + prefix_cost
        + top
        - 2
        - (exit_row + row_offset)
        + merge
        - (end + offset)
        + 4
        + merge
        - 9
        + body_cost
    )
    bound = 128 + (46 * 2 ** ((n - 6) // 2) if n % 2 == 0 else 64 * 2 ** ((n - 7) // 2))
    if cost > bound:
        return None

    def place(point: tuple[int, int]) -> tuple[int, int]:
        return point[0] + row_offset, point[1] + offset

    cells = {place(p): c for p, c in chars.items()}
    cells.update({place(p): ">'<^"[h] for p, h in turns.items()})
    checks = [
        (place(at), place(want), frozenset(place(p) for p in pending))
        for at, want, pending in reads
    ]
    cells[0, 0], cells[row_offset, 0] = "'", ">"
    cells[top - 2, end + offset] = ">"
    cells[top - 2, merge] = "'"
    chars, turns, reads, _exit, _box = _dig_flat_leaf(
        "".join(unique), [4, 2, 1], [4, 2, 1], classes=len(unique)
    )

    def below(point: tuple[int, int]) -> tuple[int, int]:
        return point[0] + top, point[1]

    cells.update({below(p): c for p, c in chars.items()})
    cells.update({below(p): ">'<^"[h] for p, h in turns.items()})
    checks.extend(
        (below(at), below(want), frozenset(below(p) for p in pending))
        for at, want, pending in reads
    )
    cells[top + 2, merge] = "<"
    last = place(halt) if bits > 4 else place((len(prefix) + 4, end))
    corridors = [
        ((0, 0), 2, row_offset),
        ((row_offset, 0), 1, offset),
        (last, 2, top - 2 - last[0]),
        ((top - 2, end + offset), 1, merge - (end + offset)),
        ((top - 2, merge), 2, 4),
        ((top + 2, merge), 3, merge - 8),
    ]
    _dig_alt_clear(cells, checks, corridors)
    return _render(cells, dense=True)
