"""One owned no-op junction drawing, derived from named lane segments."""

from typing import NamedTuple

CODE = (
    "+-------+",
    "|       |",
    "|C      |",
    "++  ++  |",
    " |  ++  |",
    " |      |",
    " |      |",
    " +------+",
)


class Surface(NamedTuple):
    """Pure primitive steering state; no native types or helpers."""

    row: int
    col: int
    heading: str
    merge: tuple | None = None
    merging_heading: str | None = None
    skip_hug: int = 0


def prefix():
    """Drive the right lane around the island, through one northbound merge."""
    result = [Surface(2, 1, "E")]
    # Named road legs, not a native-extracted state table.
    for target, heading in (
        ((2, 6), "E"),
        ((5, 6), "S"),
        ((5, 3), "W"),
        ((1, 3), "N"),
        ((1, 1), "W"),
    ):
        row, col = result[-1][:2]
        dr, dc = {"E": (0, 1), "S": (1, 0), "W": (0, -1), "N": (-1, 0)}[heading]
        while (row, col) != target:
            row, col = row + dr, col + dc
            result.append(Surface(row, col, heading))
    enriched = []
    for state in result:
        where = state.row, state.col, state.heading
        # Declining the south mouth of width2 suppresses the ordinary hug
        # for the next two cells. The junction decision itself moves first.
        skip = 2 if where == (2, 3, "E") else 1 if where == (2, 4, "E") else 0
        # At (3,3) northbound, '+' at distances2W/1E identifies a crossing.
        # Leftmost on zero is W; cross to the far north lane at row1 first.
        merge = (
            (1, 3, "left", "N", True) if where in ((2, 3, "N"), (1, 3, "N")) else None
        )
        merging = "W" if where == (1, 2, "W") else None
        enriched.append(
            Surface(state.row, state.col, state.heading, merge, merging, skip)
        )
    assert len(enriched) == 18
    assert all(CODE[s.row][s.col] in " C" for s in enriched)
    assert [i for i, s in enumerate(enriched) if s.merge is not None] == [14, 15]
    assert [i for i, s in enumerate(enriched) if s.merging_heading is not None] == [16]
    assert [i for i, s in enumerate(enriched) if s.skip_hug] == [2, 3]
    return tuple(enriched)


def parts(state):
    """All six logical components; only steering changes in this no-op prefix."""
    return (
        (
            state.row,
            state.col,
            state.heading,
            (state.merge, state.merging_heading, state.skip_hug),
        ),
        0,
        frozenset(),
        0,
        False,
        0,
    )
