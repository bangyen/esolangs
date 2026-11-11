"""ArrowQueue Boolean program generator: a Horner cascade over one row per entry.

A cascade: each stage doubles the queued markers then crosses the cell
(Horner); one ``+`` per row turns right at the indexed row.  Rows are
reached by a Horner count, so no subtree is drawn to share.  Narrow paths
drop ignored inputs too.  Constant roots halt on an empty pop or circulate
one right heading; input setters remain off those paths, as they do for
ignored cascade inputs.

Size:
    O(T) rows of one (``0``) or two (``1``) lines; n=10 and: 4,893 chars,
    4,988 cells (was 6,558). Unreachable zero-row ring halves are omitted
    ([ablations.bare_zero_runs_trick]). Constant-one setters pack outside the ring
    in rectangles of at least n + 8 cells; n=8 uses 16 cells.
    Narrow paths drop ignored inputs for area
    ([ablations.essential_projection]).
    Unbounded, the cascade or its fold into side-by-side strips
    (``_folded``: one line an entry, every exit local), whichever has the
    smaller area ([ablations.area_default]).  Mean rendered side vs the unfolded
    candidates: 68.6 -> 26.7 at n=3, 275.6 -> 41.8 at n=6, 878.6 -> 65.9 at
    n=8; none worse over all n<=3 and 30 random tables each at n=4..8.

Decisions:
    The decision tree (``n <= 4``) was never smaller at n=4 (0.0% by area, 200
    random tables) and kept ignored inputs.
    Input polarity stays lopsided (n=8 area: and 1,650 vs nor 348, nand 2,178
    vs or 354): the dropped tail is always the high-index end, and a leading
    run would need the count ``T - 1 - r``, but a stage cell pushes a bit
    (``~``) or nothing (``.``), never ``1 - bit``.  The answer is halt or
    loop, so no output flip either; no loop-less mirror exists.
"""

from collections.abc import Iterable, Iterator, Sequence
from math import isqrt
from typing import cast

from esolangs._bindings import TEMPLATE_CHAR
from esolangs.generation.helpers import (
    _validate_truth_table,
    grid_rank,
    input_weights,
    read_at,
)
from esolangs.generation.lookup import constant_output
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
)
from esolangs.generation.wrap import balance_score

#: Each input's cell: ``~`` pushes a down heading, ``.`` nothing.

_MIDDLE = ["*~* ", "*  *", "*  *", "~ ~ ", "*~* ", "**  ", "*  *"]


_INPUT = InputSlot(1)
type _Row = Sequence[TemplateToken]
_STAGE: list[_Row] = ["  *+*", (*"   ~", _INPUT), "   ~", "  **", " *~*", " *  *"]

#: An ignored input's setter, off the selector's path: either fill leaves the
#: queue as it found it, so the cascade indexes the essential inputs alone.
_IGNORED = [(*"     ", _INPUT)]

#: The same setter one column in, for the narrow paths.
_IGNORED_NARROW = [(*"    ", _INPUT)]

#: The cascade's row per table entry.  The IP enters down column 1; each ``+``
#: there pops a marker D, and the sentinel pop (heading R) leaves the queue
#: ``R D L U``.  A ``0`` row then exits right off the grid and halts.  A ``1``
#: row is a 2x3 loop of four ``+`` corners entered heading right: the first
#: lap pops R, D, L, U at its corners in order while the two ``~`` push R and
#: L back, after which the top pair bounces forever.  Tested in
#: ``test_ring_pops_rdlu_then_sustains``.
_ROWS = {"0": [" +"], "1": [" + +~+", "   +~+"]}

#: A folded tail of ``1`` rows: every marker left laps the ``*`` square back
#: into one ``+``; the stop heading then enters the ring as on a ``1`` row.
_DRAINED_RING = ["*+ +~+", "** +~+"]


def arrowqueue(truth_table: str, width: int | None = None) -> str:
    """Build an ArrowQueue template that halts iff the table entry is ``0``.

    Unbounded, the smaller by area of the unfolded cascade and the folds.
    """
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    program = _program(truth_table, width)
    if width is None and constant_output(truth_table) is None:
        return min(
            (program, *_folds(truth_table)), key=lambda layout: grid_rank(layout.source)
        )
    return program


def _render_grid(rows: Iterable[_Row]) -> TemplateLayout:
    def parts() -> Iterator[TemplateToken]:
        for i, row in enumerate(rows):
            if i:
                yield "\n"
            if isinstance(row, str):
                yield row.rstrip()
                continue
            last = len(row)
            while last and row[last - 1] == " ":
                last -= 1
            yield from row[:last]

    return layout_fragments(parts())


def _constant_ring(n: int, width: int) -> TemplateLayout:
    """Pack ignored setters outside the one-heading ring's eight visited cells."""
    height = max(3, -(-(n + 8) // width))
    rows: list[list[TemplateToken]] = [[" "] * width for _ in range(height)]
    ring = {
        (0, 0): "~",
        (0, 1): "*",
        (1, 1): "+",
        (1, 2): "~",
        (1, 3): "*",
        (2, 1): "*",
        (2, 2): " ",
        (2, 3): "*",
    }
    for (row, col), char in ring.items():
        rows[row][col] = char
    left = n
    for row in range(height):
        for col in range(width):
            if left and (row, col) not in ring:
                rows[row][col] = _INPUT
                left -= 1
    assert left == 0
    return _render_grid(rows)


def _program(truth_table: str, width: int | None = None) -> TemplateLayout:
    """Build the marker cascade, or a direct constant halt/ring."""
    n = _validate_truth_table(truth_table)
    if (constant := constant_output(truth_table)) is not None:
        if constant == "0":
            return _render_grid(("+", *((_INPUT,),) * n))
        if n >= 3:
            forms = [_constant_ring(n, 4), _constant_ring(n, max(4, -(-(n + 8) // 3)))]
            best = min(forms, key=lambda layout: grid_rank(layout.source))
            if width is None or max(map(len, best.source.splitlines())) <= max(
                4, width
            ):
                return best
            return _constant_ring(n, max(4, width))
        # The initial ~ supplies R to the top-left +. The ring's top ~
        # replenishes it before three clockwise corners return to that +.
        # Column zero below the entry is never visited, so either setter
        # leaves the ring's one-heading queue and path alone.
        return _render_grid(
            (
                "~*",
                (_INPUT, *"+~*"),
                (_INPUT if n > 1 else " ", *"* *"),
            )
        )
    width = max(width or 0, 0)  # 0, None and negative all mean unbounded
    weights, table = input_weights(truth_table, n)
    if 0 < width < 5:
        return _four_column_cascade(table, weights)
    narrow = 0 < width < 6
    leaves = _cascade(table)
    if narrow:
        leaves = [row[:2] + row[3:] for row in leaves]
    ignored = _IGNORED_NARROW if narrow else _IGNORED
    stages = [row for weight in weights for row in (_STAGE if weight else ignored)]
    rows: list[_Row] = ["  ~*", *stages, *_MIDDLE, *leaves]
    return _render_grid(rows)


def _four_column_cascade(table: str, weights: Sequence[int]) -> TemplateLayout:
    """Prepend a down marker to route the selector along column0."""
    # Shift input stages left; a clockwise detour lands down at column 1.
    stages = (row[1:] for w in weights for row in (_STAGE if w else _IGNORED_NARROW))
    rows: list[_Row] = [" ~*", *stages, "**", "* *", " ~"]
    # Append D, rotate the D markers to the R sentinel; queue becomes D^(index+1),R.
    rows.extend(["*+~*", " ~", "**"])
    rows.extend(_MIDDLE)
    # The extra D turns leftward travel down; consuming it restores the queue.
    rows.append("+*")
    for bit in table:
        # Unfold the constant tail: its old drain loop uses column0.
        rows.extend((row[:2] + row[3:])[1:] for row in _ROWS[bit])
    return _render_grid(rows)


def _cascade(truth_table: str) -> list[str]:
    """Build the cascade's rows, the table's constant tail folded.

    A ``0`` tail is dropped (running off the grid halts); a ``1`` tail is
    one :data:`_DRAINED_RING`, popping the markers the dropped rows would.
    """
    tail = len(truth_table.rstrip(truth_table[-1]))
    rows = [row for bit in truth_table[:tail] for row in _ROWS[bit]]
    return [*rows, *_DRAINED_RING] if truth_table[-1] == "1" else rows


#: A folded cascade's line per entry.  A sentinel pop leaves heading R with the
#: queue ``R D L U``; a ``1`` laps the ``+~+`` ring the next line closes, a ``0``
#: halts on an empty pop in the 2x2 of ``+`` below its own (the next line's
#: column-2 ``+``, or its leaf ``+`` when that is blank).  Every exit stays in
#: rows r, r+1 and columns 1..5, so strips stand side by side.
_LEAF = {"0": " +++~+", "1": " + +~+"}

#: The line below a strip's last entry: the ring's lower half, or only the
#: two ``+`` a zero exit needs.  Columns 0 and 1 stay free for a fold's corridor.
_LEAF_END = {"0": "  ++", "1": "   +~+"}

#: Lines, entry column, exit column; the IP enters and leaves heading down.
type _Block = tuple[Sequence[_Row], int, int]


def _folded(table: str, height: int) -> TemplateLayout | None:
    """Fold the cascade into side-by-side strips at most ``height`` rows tall.

    Each strip but the last ends in a corridor: ``*`` turns left below its
    exit, ``*`` turns up its column 0, a lane clear to the top, where ``*``
    turns right along row 1 (even strips) or row 0 (odd), across to the next
    strip's entry ``*``.  Alternating the rows lets each crossing pass the
    next lane where it is blank.  A strip whose column 0 is used (the middle)
    shifts right one.  Templates fill in reading order, so stage ``j`` reads
    the input its setter ranks; leaves are indexed in that order.  ``None``
    when that order puts an ignored setter where a stage stands, or when one
    strip holds everything.  ``height`` >= 10 fits the middle.
    """
    n = _validate_truth_table(table)
    weights, _ = input_weights(table, n)
    cap = height - 3
    strips: list[list[_Block]] = [[]]
    used = [0]

    def place(block: _Block) -> None:
        if used[-1] + len(block[0]) > cap:
            strips.append([])
            used.append(0)
        strips[-1].append(block)
        used[-1] += len(block[0])

    setters = []  # (row, strip, chain position)
    for j, weight in enumerate(weights):
        place((_STAGE if weight else _IGNORED_NARROW, 3, 3))
        row = used[-1] - len(strips[-1][-1][0]) + (1 if weight else 0)
        setters.append((row, len(strips) - 1, j))
    place((_MIDDLE, 3, 1))
    reads = [0] * n
    for rank, (_row, _strip, j) in enumerate(sorted(setters)):
        if bool(weights[j]) != bool(weights[rank]):
            return None
        reads[j] = rank
    leaves = read_at(table, [reads[j] for j in range(n) if weights[j]], n)
    tail = len(leaves.rstrip(leaves[-1]))
    # Only a preceding one uses the lower ring at columns 4/5.  The selector
    # stays in column 1, zero halts in columns 2/3, and corridors stay outside.
    lines = [
        " +++" if bit == "0" and i and leaves[i - 1] == "0" else _LEAF[bit]
        for i, bit in enumerate(leaves[:tail])
    ]
    blocks: list[_Block] = [([line], 1, 1) for line in lines]
    if leaves[-1] == "1":
        blocks.append((_DRAINED_RING, 1, 1))
    else:
        blocks[-1] = ([lines[-1], _LEAF_END["1"]], 1, 1)
    for block in blocks:
        place(block)
    if len(strips) == 1:
        return None
    return _render_strips(strips)


def _render_strips(strips: list[list[_Block]]) -> TemplateLayout:
    """Draw ``strips`` from row 2 with their corridors; see :func:`_folded`."""
    last = len(strips) - 1
    shifts = [
        int(i < last and any(line and line[0] != " " for b in strip for line in b[0]))
        for i, strip in enumerate(strips)
    ]
    widths = [
        shift + max(len(line) for b in strip for line in b[0])
        for shift, strip in zip(shifts, strips, strict=True)
    ]
    heights = [
        2 + sum(len(b[0]) for b in strip) + (i < last) for i, strip in enumerate(strips)
    ]
    grid = [[" "] * sum(widths) for _ in range(max(heights))]
    slots: dict[int, list[int]] = {}
    x = 0
    entries = []
    for i, strip in enumerate(strips):
        left = x + shifts[i]
        entries.append(left + strip[0][1])
        row = 2
        for lines, _entry, _exit in strip:
            for line in lines:
                if isinstance(line, str):
                    grid[row][left : left + len(line)] = line
                else:
                    column = left + len(line) - 1
                    grid[row][left:column] = cast("Sequence[str]", line[:-1])
                    grid[row][column] = TEMPLATE_CHAR
                    slots.setdefault(row, []).append(column)
                row += 1
        if i < last:
            lines, _entry, exit_col = strip[-1]
            if lines[-1] in (*_LEAF.values(), " +++"):
                below = _LEAF_END["0" if lines[-1] in (_LEAF["0"], " +++") else "1"]
                grid[row][left : left + len(below)] = below
            grid[row][x] = grid[row][left + exit_col] = "*"
        x += widths[i]
    grid[0][entries[0] - 1 : entries[0] + 1] = "~*"
    x = 0
    for i in range(last):
        grid[1 - i % 2][x] = grid[1 - i % 2][entries[i + 1]] = "*"
        x += widths[i]
    rendered = ["".join(row).rstrip() for row in grid]
    spans: list[tuple[int, int]] = []
    offset = 0
    for row, line in enumerate(rendered):
        spans.extend(
            (offset + column, offset + column + 1) for column in slots.get(row, ())
        )
        offset += len(line) + 1
    return TemplateLayout("\n".join(rendered), tuple(spans))


def _folds(table: str) -> list[TemplateLayout]:
    """Folds at distinct heights around where the strips' width meets twice the height.

    A fold is ``F`` lines (``6n + 7 +`` one a table entry) cut into strips of
    ``h - 3`` rows, each about 6 columns wide: ``2h = 6F / (h - 3)``, so
    ``h = (3 + sqrt(9 + 12F)) / 2``.  That lands within one row of the best
    height at n=3..10 (4 random tables each; e.g. 59 vs 58-60 at n=10).
    """
    n = _validate_truth_table(table)
    lines = 6 * n + 7 + len(table)
    centre = (3 + isqrt(9 + 12 * lines)) // 2
    heights = dict.fromkeys(max(10, height) for height in range(centre - 1, centre + 3))
    folds = (_folded(table, height) for height in heights)
    return [fold for fold in folds if fold is not None]


def arrowqueue_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def arrowqueue_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Return the default or the fold with the least balanced side."""
    default = request.source
    if not isinstance(default, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    if constant_output(request.table) is not None:
        return default
    return min(
        (default, *_folds(request.table)),
        key=lambda layout: balance_score(layout.source),
    )
