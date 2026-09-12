r"""Boolean-function generator for Alight."""

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["alight"]

# : The two turns a fold spends.
# : cell* and the next command.
# : so a fold is two of them:.
# : downward to face along the.
# : right of east is south and.
# : lefts to get from west back.
_ALIGHT_EAST_TURN = "turn right;"
_ALIGHT_WEST_TURN = "turn left;"


def _alight_chunk(rows: int, width: int) -> int:
    r"""How many table entries one lookup may carry, inside ``width``."""
    index = len(f"{rows - 0.5}")
    # ``skip i < I;`` is 10 + I,.
    overhead = 28 + 2 * index
    chunk = max(1, width - overhead - len(_ALIGHT_EAST_TURN))
    # Chunking is not free: it buys.
    # a short table the guard costs.
    # the whole table in one lookup.
    # make the widest unit narrower.
    # otherwise asking for 1 came.
    # not what "the narrowest it.
    if len('set r at{"", i+0.5};') + rows <= overhead + chunk:
        return rows
    return chunk


def _alight_units(truth_table: str, n: int, chunk: int) -> list[list[str]]:
    r"""Build the commands, grouped into pieces a fold may not split."""
    units: list[list[str]] = [["begin"], ["var a"], ["var i"], ["var r"]]
    for k in range(n):
        units.append(["inp a"])
        units.append(
            [f"set i a-{_ASCII_ZERO}" if k == 0 else f"set i i*2+a-{_ASCII_ZERO}"]
        )
    rows = len(truth_table)
    if chunk >= rows:
        # Indices run 0.5, 1.5, .
        units.append([f'set r at{{"{truth_table}", i+0.5}}'])
    else:
        for start in range(0, rows, chunk):
            piece = truth_table[start : start + chunk]
            if start == 0:
                units.append(
                    [
                        f"skip i > {start + len(piece) - 0.5}",
                        f'set r at{{"{piece}", i+0.5}}',
                    ]
                )
            else:
                low = start - 0.5
                units.append([f"skip i < {low}", f'set r at{{"{piece}", i-{low}}}'])
    units.append(["out r"])
    units.append(["end"])
    return units


def _alight_folded(units: list[list[str]], width: int) -> str:
    r"""Lay ``commands`` out as a boustrophedon inside ``width`` columns."""
    longest = max(len(";".join(unit)) for unit in units) + 1
    # Every row runs the full span,.
    # row has to hold; a narrower.
    limit = max(width, longest + len(_ALIGHT_EAST_TURN) + 1)
    cells: dict[tuple[int, int], str] = {}
    row, col, step = 0, 0, 1
    pending = list(units)
    # Every pass places at least.
    # ``pending`` leaves through.
    # way out and says so.
    while True:
        turn = _ALIGHT_EAST_TURN if step == 1 else _ALIGHT_WEST_TURN
        edge = limit - 1 if step == 1 else 0
        turn_start = edge - step * (len(turn) - 1)
        room = abs(turn_start - col)
        taken: list[str] = []
        used = 0
        while pending:
            piece = ";".join(pending[0]) + ";"
            if taken and used + len(piece) > room:
                break
            taken.append(piece)
            used += len(piece)
            pending.pop(0)
        for i, char in enumerate("".join(taken)):
            cells[row, col + i * step] = char
        col += step * used
        if not pending:
            break
        while col != turn_start:
            cells[row, col] = ";"
            col += step
        for i, char in enumerate(turn):
            cells[row, col + i * step] = char
        col = edge
        for i, char in enumerate(turn):
            cells[row + 1 + i, col] = char
        row += len(turn)
        step = -step
        col += step
    if min(c for _, c in cells) < 0:
        raise AssertionError("a run walked off the left edge")
    height = max(r for r, _ in cells) + 1
    ends: dict[int, int] = {}
    for r, c in cells:
        ends[r] = max(ends.get(r, 0), c)
    # A row is trimmed to its last.
    # ``turn right`` has a space in.
    # blank that is part of a.
    return "\n".join(
        "".join(cells.get((r, c), " ") for c in range(ends.get(r, -1) + 1))
        for r in range(height)
    )


def alight(truth_table: str, width: int | None = None) -> str:
    r"""Return an Alight program printing ``truth_table``'s entry for its."""
    n = _validate_truth_table(truth_table)
    flat = ";".join(
        ";".join(u) for u in _alight_units(truth_table, n, len(truth_table))
    )
    flat += ";"
    if width is None or len(flat) <= width:
        return flat
    units = _alight_units(truth_table, n, _alight_chunk(len(truth_table), width))
    return _alight_folded(units, width)
