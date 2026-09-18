"""Boolean-function generator for Back."""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
)

#: Finisher for a cell primed to 1: ``-`` flips it to 0, ``+`` is inert.
#: Both are one grid cell, so a run is the exact width of its program.
PAIR = ("-", "+")
_BACK_INPUT = TEMPLATE_CHAR * len(PAIR[0])


def _reflect_back(grid: dict[tuple[int, int], str], height: int, width: int) -> str:
    r"""Reflect a Back template and route the fixed eastward start into it.

    ``grid`` maps ``(row, column)`` to a character; ``width`` is the widest
    row.  An input's run is one grid cell like every other character, so
    reflection reverses cells.  Only the beam mirrors swap; ``<`` and ``>``
    move the tape head and keep their meanings.  Rendered from the sparse
    cells, each row only as long as its last one, so the cost is the
    output's size rather than the bounding box (``2**n`` rows by ``4n``).
    """
    mirrors = {"/": "\\", "\\": "/"}
    rows: list[dict[int, str]] = [{} for _ in range(height)]
    for (row, column), cell in grid.items():
        rows[row][width - column] = mirrors.get(cell, cell)

    # East, south, wrap west, north, west into the reflected root.  The two
    # extra columns touch only rows 0-1; tree padding is trailing and rstrips.
    rows[0][0] = rows[0][width + 1] = "\\"
    rows[1][0] = "/"
    rows[1][width + 1] = "\\"
    lines = []
    for cells in rows:
        line = [" "] * (max(cells, default=-1) + 1)
        for column, cell in cells.items():
            line[column] = cell
        lines.append("".join(line))
    return "\n".join(lines)


def back(truth_table: str) -> str:
    r"""Build a Back template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Back is a no-input grid language: a beam travels the grid and ``-`` flips
    the current tape bit, ``+`` steps the beam forward when the current bit
    is 0, ``<``/``>`` move the tape pointer, ``\`` reflects the beam down,
    and ``*`` halts printing the tape.  Each input is embedded once by
    filling its tape cell over two load rows: a constant ``-`` primes the
    cell to 1 for either bit, then the input's run finishes it -- ``+`` (inert on
    a set cell) for a one, ``-`` (flipping it back) for a zero.  So cells
    ``0..n-1`` hold the inputs and cell ``n`` is the answer cell.  Both
    bits cost the same two rows and, because no ``+`` ever meets a zero
    cell here, both rows run for either bit.  A zero used to embed as a
    blank the rstrip then removed, which made the program's height reveal
    it.

    A decision node is ``+\>``: ``+`` tests the current tape bit (advancing
    the beam straight past the ``\`` when it is 0) and ``\`` reflects the
    beam down when it is 1, while ``>`` advances the tape pointer to the next
    input.  Both branches advance the pointer once, so a leaf at depth ``d``
    has the pointer at cell ``d``.  A leaf walks to cell ``n``, flips it with
    ``-`` when its value is 1, and halts.

    The load runs *down column 0* and the tree starts at column 1, so no row
    carries the load's width as indent.  A ``/`` at the origin does both
    turns: the beam starts heading right, the ``/`` sends it up and off the
    top edge onto the bottom row, it runs the load upward back to the origin,
    and the ``/`` -- now taking a beam heading up -- turns it right into the
    tree.  The load is written bottom-to-top, and the drawing is reflected
    for output, so the tree grows left and its triangular padding lands at
    line ends where it is stripped.  A two-row outer route converts Back's
    fixed eastward start into the westward entry the reflected root needs.

    The answer is the *value* of cell ``n``, which the halt dump prints,
    rather than the head's position, which it does not.  An earlier layout
    parked the head on whichever of a 0-cell and a 1-cell matched, which made
    the result unreadable from the program's own output.  One answer cell
    costs a leaf one ``-`` instead of one extra pointer move.
    """
    n = _validate_truth_table(truth_table)
    return _back_ordered(truth_table, tuple(range(n)))


def _back_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Build one Back template, loading its inputs in ``perm`` order.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame.  ``perm`` is spent in exactly one place: the cell each
    input's unit loads into.

    A node is ``+\>`` -- test the current cell, *then* advance -- so level
    ``k`` tests cell ``k``, and input ``perm[k]`` is the one that has to be
    loaded there.  That is one cell lower than the generators whose node
    steps before it tests (Streetcode's halls and LaserFuck's ``>#v)`` both
    test cell ``k + 1``), and getting it wrong computes a different
    function rather than failing to draw.

    **The load runs the inputs in name order and walks the pointer to
    each one's cell.**  Input ``i`` belongs at cell ``perm.index(i)``, the
    inverse of the permutation, and a walk of ``>``/``<`` carries the
    pointer there.  Reading the permutation forward instead puts the right
    bits in the wrong cells and computes a different function.

    **This is not the cheapest build, and the trade is deliberate.**
    Filling in *cell* order -- cell ``c`` taking input ``perm[c]`` -- emits no
    walk at all and delivers the full 12.0% screen against the 9.15% here,
    but it puts the inputs out of name order, and the k-th run of the
    template *is* input k: the harness fills the runs in order, so a
    cell-order load would have to carry its permutation some other way.
    The choice costs 2.85 points.  The walk is cheap in absolute
    terms and shows up at all only because Back's programs are small -- 82
    characters on average at n=3, against LaserFuck's 326.

    Keeping the ``-``/run pairs intact preserves the equal-width
    embedding: the primer and the run are one unit and are never
    separated, so both bits still cost the same two rows and the template's
    height cannot leak an input.
    """
    n = _validate_truth_table(truth_table)

    # Level c tests cell c and input perm[c], so input i lives at cell
    # perm.index(i).  Filling in cell order instead needs no walk (12.0% vs
    # 9.15%) but breaks "run k = input k"; not kept -- see the docstring.
    cells = [0] * n
    for level, i in enumerate(perm):
        cells[i] = level

    def walk(frm: int, to: int) -> list[str]:
        """Move the pointer from cell ``frm`` to cell ``to``, one per row."""
        return [">" if to >= frm else "<"] * abs(to - frm)

    # Reverse name order: the load is drawn bottom-up in column 0, so this
    # emits input 0 first.  The input-order search prices the walk anyway.
    units: list[str] = []
    at = 0
    for cell in range(n - 1, -1, -1):
        # Primer '-' then the run, one row each (the beam reads one cell per
        # row).  Bit on the trailing row so every load row executes; the walk
        # goes before the pair, never between, or the height leaks the bit.
        units.extend(walk(at, cells[cell]))
        units.append("-")
        units.append(_BACK_INPUT)
        at = cells[cell]
    # Open the answer cell at n, then home to cell 0.
    units.extend(walk(at, n))
    units.extend("<" * n)

    # One '/' at the origin does both turns: right -> up off the top edge onto
    # the bottom row, up the load, then up -> right into the tree at column 1.
    # Relies on toroidal wrap (``_Machine.step`` uses ``% len(code)``); the
    # wiki text is silent on edges and no interpreter test covers a wrap.
    grid: dict[tuple[int, int], str] = {}
    next_row = [1]
    constant = constant_span_test(truth_table)

    def leaf(level: int, value: str, row: int, col: int) -> None:
        # Walk to cell n, flip it (starts 0) for a 1-leaf, halt.
        delta = n - level
        move = (">" if delta >= 0 else "<") * abs(delta)
        code = move + ("-" if value == "1" else "") + "*"
        for k, ch in enumerate(code):
            grid[(row, col + k)] = ch

    def emit(level: int, lo: int, hi: int, row: int, col: int) -> None:
        if level == n or constant(lo, hi):
            leaf(level, truth_table[lo], row, col)
            return
        mid = lo + (hi - lo) // 2
        grid[(row, col)] = "+"
        grid[(row, col + 1)] = "\\"
        grid[(row, col + 2)] = ">"
        emit(level + 1, lo, mid, row, col + 3)  # zero (bit=0) straight
        nrow = next_row[0]
        next_row[0] += 1
        grid[(nrow, col + 1)] = "\\"
        grid[(nrow, col + 2)] = ">"
        emit(level + 1, mid, hi, nrow, col + 3)  # one (bit=1) child

    emit(0, 0, 2**n, 0, 1)  # tree root at column 1, the beam arriving rightward

    # Height is max(tree 2**n, load units + 1).  Past n=3 load rows share with
    # tree rows; safe only because a run is one character for either bit.
    height = max(max(r for r, _ in grid) + 1, 1 + len(units))
    width = max(c for _, c in grid) + 1
    grid[(0, 0)] = "/"
    for k, unit in enumerate(units):
        grid[(height - 1 - k, 0)] = unit
    # No input row can instantiate to whitespace (a zero used to embed as a
    # blank, and the height revealed it).
    return _reflect_back(grid, height, width)
