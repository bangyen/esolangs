"""Draw stacked Flowchart trees and route jumps to shared subtrees."""

from collections import Counter
from collections.abc import Callable, Sequence
from enum import Enum

from esolangs.generation.helpers import subtree_ids
from esolangs.languages.flowchart._layout import (
    _answer_column,
    _folded_walk,
    _paint,
    _plan,
    _set,
)

# Fewest table rows a subtree must span for the stacked layout to draw it once.
_SHARE_ROWS = 8


def _shareable(
    ids: Sequence[Sequence[int]],
    counts: list[Counter[int]],
    depth: int,
    lo: int,
    hi: int,
) -> int | None:
    """Return the subtree id if the span is drawn once and shared, else None.

    A span is shared when it covers at least ``_SHARE_ROWS`` rows and its
    subtree id repeats at this depth.  Constant spans have ids 0/1 and are
    never shared.
    """
    if hi - lo < _SHARE_ROWS:
        return None
    sid = ids[depth][lo // (hi - lo)]
    return sid if sid >= 2 and counts[depth][sid] > 1 else None


def _occurrences(ids: Sequence[Sequence[int]]) -> Counter[int]:
    """Count repeated drawings, one-branch first.

    Stop at each shared root: a path may jump only once.
    """
    counts = [Counter(level) for level in ids]
    found: Counter[int] = Counter()
    levels = len(ids) - 1

    def visit(depth: int, block: int) -> None:
        if ids[depth][block] < 2:
            return
        span = 1 << (levels - depth)
        lo = block * span
        sid = _shareable(ids, counts, depth, lo, lo + span)
        if sid is None:
            visit(depth + 1, 2 * block + 1)
            visit(depth + 1, 2 * block)
        else:
            found[sid] += 1

    visit(0, 0)
    return found


_Cursor = tuple[int, bool]


class _Role(Enum):
    """How the stacked layout draws one branch's subtree."""

    PLAIN = "plain"
    JUMP = "jump"  # an earlier copy of a shared subtree: a rail to the last
    BODY = "body"  # the last copy, drawn once and entered from the east


class _Stacked:
    """Painter state for the stacked layout; ``cursor`` is ``(row, locked)``."""

    def __init__(self, truth_table: str, *, share: bool) -> None:
        self.truth_table, self.costs, self.tail = _plan(truth_table)
        # Columns 0..n-1 are the corridors, one per depth; the tree itself
        # sits on ``spine``, far enough east that the answer's ``(( ))``
        # clears them.
        self.spine = len(self.costs) + 2
        self.bus = self.spine + 3
        self.cells: dict[tuple[int, int], str] = {}
        self.taps: list[int] = []
        self.share = share
        self.ids = subtree_ids(self.truth_table)
        self.counts = [Counter(level) for level in self.ids] if share else []
        self.copies = _occurrences(self.ids) if share else Counter[int]()
        self.seen: Counter[int] = Counter()
        self.entries: dict[int, int] = {}
        # (row, first column east, id) of each copy drawn as a jump.
        self.jumps: list[tuple[int, int, int]] = []

    def is_constant(self, lo: int, hi: int) -> bool:
        """Classify a dyadic span from the already indexed canonical subtree."""
        span = hi - lo
        return self.ids[len(self.ids) - span.bit_length()][lo // span] < 2

    def reads(self, y: int, count: int) -> int:
        """Draw ``count`` ``/ /`` nodes down the spine; return the row after."""
        for _ in range(count):
            _paint(self.cells, self.spine - 1, y, "/ /")
            self.cells[(self.spine, y + 1)] = "│"
            y += 2
        return y

    def paint_leaf(self, lo: int, depth: int, cursor: _Cursor) -> _Cursor:
        """Draw the leaf for ``truth_table[lo]``, entered at ``(spine, y)``.

        A folded leaf's owed reads stack above it.  Returns the row below
        the leaf and the unchanged lock flag.
        """
        cells, spine = self.cells, self.spine
        y, locked = cursor
        y = self.reads(y, sum(self.costs[depth:]) + self.tail)
        _paint(cells, spine - 1, y, _set(self.truth_table[lo]))
        cells[(spine, y + 1)] = "│"
        _paint(cells, spine, y + 2, "└──")
        self.taps.append(y + 2)
        return y + 3, locked

    def classify(
        self, lo: int, hi: int, depth: int, *, locked: bool
    ) -> tuple[int | None, _Role]:
        """Return the span's repeating subtree id (or ``None``) and its role.

        A candidate that never repeats in a drawn copy is ``PLAIN`` but its id
        is still returned: the descent below it stays locked.
        """
        if not self.share or locked:
            return None, _Role.PLAIN
        sid = _shareable(self.ids, self.counts, depth, lo, hi)
        if sid is None or self.copies[sid] < 2:
            return sid, _Role.PLAIN
        self.seen[sid] += 1
        last = self.seen[sid] == self.copies[sid]
        return sid, _Role.BODY if last else _Role.JUMP

    def paint_branch(
        self,
        lo: int,
        hi: int,
        depth: int,
        cursor: _Cursor,
        descend: Callable[[int, int, int, _Cursor], _Cursor],
    ) -> _Cursor:
        """Draw the subtree for ``truth_table[lo:hi]``; return the row after."""
        y, locked = cursor
        y = self.reads(y, self.costs[depth])
        _paint(self.cells, self.spine - 1, y, "< >")
        half = (hi - lo) // 2
        below = self._one_branch(lo + half, hi, depth, y, descend, locked=locked)
        return self._zero_branch(lo, lo + half, depth, y, below, descend, locked=locked)

    def _enter_from_east(self, y: int, corner: str) -> None:
        """Paint the detour west from ``spine + 2`` onto the spine at row ``y``."""
        self.cells[(self.spine + 2, y)] = corner
        self.cells[(self.spine + 1, y)] = "─"
        self.cells[(self.spine, y)] = "┌"

    def _one_branch(
        self,
        lo: int,
        hi: int,
        depth: int,
        y: int,
        descend: Callable[[int, int, int, _Cursor], _Cursor],
        *,
        locked: bool,
    ) -> int:
        """Draw b=1: east out of the switch, down, back west onto the spine.

        Returns the row below it, where the zero-branch's rail ends.
        """
        cells, spine = self.cells, self.spine
        cells[(spine + 2, y)] = "┐"
        one, how = self.classify(lo, hi, depth + 1, locked=locked)
        if how is _Role.JUMP:
            assert one is not None
            cells[(spine + 2, y + 1)] = "└"
            self.jumps.append((y + 1, spine + 3, one))
            return y + 2
        self._enter_from_east(y + 1, "┴" if how is _Role.BODY else "┘")
        if one is not None and how is _Role.BODY:
            self.entries[one] = y + 1
        below, _ = descend(lo, hi, depth + 1, (y + 2, locked or one is not None))
        return below

    def _zero_branch(
        self,
        lo: int,
        hi: int,
        depth: int,
        y: int,
        below: int,
        descend: Callable[[int, int, int, _Cursor], _Cursor],
        *,
        locked: bool,
    ) -> _Cursor:
        """Draw b=0: west to this depth's own column, down past the one-branch.

        Then east again onto the spine.
        """
        cells, spine = self.cells, self.spine
        for x in range(depth + 1, spine - 1):
            cells[(x, y)] = "─"
        cells[(depth, y)] = "┌"
        for row in range(y + 1, below):
            cells[(depth, row)] = "│"
        cells[(depth, below)] = "└"
        zero, how = self.classify(lo, hi, depth + 1, locked=locked)
        if how is _Role.JUMP:
            assert zero is not None
            for x in range(depth + 1, spine + 2):
                cells[(x, below)] = "─"
            self.jumps.append((below, spine + 2, zero))
            return below + 1, locked
        for x in range(depth + 1, spine + 2 if how is _Role.BODY else spine):
            cells[(x, below)] = "─"
        if how is _Role.PLAIN:
            cells[(spine, below)] = "┐"
            return descend(lo, hi, depth + 1, (below + 1, locked or zero is not None))
        # A repeated zero-branch is entered from the east like a one-branch.
        cells[(spine + 2, below)] = "┐"
        self._enter_from_east(below + 1, "┴")
        assert zero is not None
        self.entries[zero] = below + 1
        return descend(lo, hi, depth + 1, (below + 2, True))

    def close(self) -> None:
        """Paint the answer, then the bus joining every leaf tap to it."""
        cells, spine, bus, taps = self.cells, self.spine, self.bus, self.taps
        _paint(cells, spine - 1, 0, "( )")
        cells[(spine, 1)] = "│"
        # Heading east onto ``┤`` turns clockwise, down, so every tap joins.
        for row in range(taps[0], taps[-1] + 1):
            cells[(bus, row)] = "│"
        for row in taps:
            cells[(bus, row)] = "┤"
        cells[(bus, taps[0])] = "┐"
        end = taps[-1] + 1
        cells[(bus, end)] = "┘"
        _paint(cells, spine, end, "┌──")
        _answer_column(cells, spine, end + 1)
        _join_jumps(cells, self.jumps, self.entries, spine)


def _flowchart_stacked(
    truth_table: str, *, share: bool = False
) -> dict[tuple[int, int], str]:
    """Paint the tree with its subtrees stacked rather than side by side.

    The one-branch hangs below the switch and the zero-branch falls down its
    own column past it, so every node shares one column and width costs
    height.  A downward switch sends 1 east and 0 west, so each branch is
    caught by a corner: the one-branch steps east and back, the zero-branch
    runs west to the column reserved for its depth and back.  Corridor ``d``
    is column ``d`` and every descendant is deeper and further east, so no
    rail and corridor ever meet.  Each leaf turns east onto a bus down
    column ``spine + 3``, which returns to the spine below the last leaf.

    With ``share``, a subtree of ``_SHARE_ROWS`` rows or more that repeats at
    its depth is drawn once, at its last copy.  Its entry is the east detour's
    ``┴``, which a pointer from above and one from the east both leave west;
    each earlier copy runs east over the bus to a rail column (``spine + 4``
    on) and down to the entry row.  A pointer may not cross a cell it already
    left (it would take the exit remembered from the first pass), and its
    later way down the bus starts below the entry row, so the rails must run
    down to the copy; running up to it would cross that bus.
    """
    painter = _Stacked(truth_table, share=share)
    _folded_walk(
        len(painter.truth_table),
        painter.is_constant,
        painter.paint_leaf,
        painter.paint_branch,
        (2, False),
    )
    painter.close()
    return painter.cells


def _join_jumps(
    cells: dict[tuple[int, int], str],
    jumps: list[tuple[int, int, int]],
    entries: dict[int, int],
    spine: int,
) -> None:
    """Draw each copy's rail down to the entry row of its drawn subtree.

    The topmost copy of an id is the trunk: east along its row, down column
    ``spine + 4 + k`` and west along the entry row to the ``┴``.  A lower copy
    runs east along its own row and turns down onto the trunk at ``┤`` (a
    pointer heading east onto it turns down).  Groups whose spans are apart
    share a column; crossings (the bus, other rails) become ``┼``.
    """

    def put(x: int, y: int, char: str) -> None:
        crossing = {cells.get((x, y)), char} == {"│", "─"}
        cells[(x, y)] = "┼" if crossing else char

    last_row: list[int] = []  # per rail column, the entry row it reaches
    groups: dict[int, list[tuple[int, int]]] = {}
    for row, start, sid in jumps:
        groups.setdefault(sid, []).append((row, start))
    for sid in sorted(groups, key=lambda sid: min(groups[sid])):
        copies = sorted(groups[sid])
        top, entry = copies[0][0], entries[sid]
        column = next((k for k, end in enumerate(last_row) if end < top), None)
        if column is None:
            column = len(last_row)
            last_row.append(entry)
        else:
            last_row[column] = entry
        x = spine + 4 + column
        for y in range(top + 1, entry):
            put(x, y, "│")
        cells[(x, entry)] = "┘"
        for i in range(spine + 3, x):
            put(i, entry, "─")
        for number, (row, start) in enumerate(copies):
            for i in range(start, x):
                put(i, row, "─")
            cells[(x, row)] = "┐" if number == 0 else "┤"
