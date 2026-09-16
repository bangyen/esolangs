"""Boolean-function generator for Back."""

import re

from esolangs.tools.helpers import _validate_truth_table, constant_span_test


def _reflect_back(source: str) -> str:
    r"""Reflect a Back template and route the fixed eastward start into it.

    A placeholder is one grid cell despite occupying several source
    characters, so reflection reverses parsed cells rather than characters.
    Only the beam mirrors swap; ``<`` and ``>`` move the tape head and keep
    their meanings.
    """
    rows = [re.findall(r"\{X\d+\}|.", row) for row in source.splitlines()]
    width = max(map(len, rows))
    mirrors = str.maketrans({"/": "\\", "\\": "/"})
    reflected: list[list[str]] = []
    for row in rows:
        cells = list(reversed([*row, *([" "] * (width - len(row)))]))
        reflected.append(
            [
                " ",
                *(
                    cell.translate(mirrors) if len(cell) == 1 else cell
                    for cell in cells
                ),
                " ",
            ]
        )

    # Start east, turn south, wrap west, then turn north and west into the
    # reflected root.  The two extra columns touch only these first rows;
    # all tree padding is now trailing and disappears under rstrip.
    reflected[0][0] = reflected[0][-1] = "\\"
    reflected[1][0] = "/"
    reflected[1][-1] = "\\"
    return "\n".join("".join(row).rstrip() for row in reflected)


def back(truth_table: str) -> str:
    r"""Build a Back template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Back is a no-input grid language: a beam travels the grid and ``-`` flips
    the current tape bit, ``+`` steps the beam forward when the current bit
    is 0, ``<``/``>`` move the tape pointer, ``\`` reflects the beam down,
    and ``*`` halts printing the tape.  Each input is embedded once by
    filling its tape cell over two load rows: a constant ``-`` primes the
    cell to 1 for either bit, then ``{Xi}`` finishes it -- ``+`` (inert on
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
    ``{Xi}`` unit loads into.

    A node is ``+\>`` -- test the current cell, *then* advance -- so level
    ``k`` tests cell ``k``, and input ``perm[k]`` is the one that has to be
    loaded there.  That is one cell lower than the generators whose node
    steps before it tests (Streetcode's halls and LaserFuck's ``>#v)`` both
    test cell ``k + 1``), and getting it wrong computes a different
    function rather than failing to draw.

    **The load runs the placeholders in name order and walks the pointer to
    each one's cell.**  Input ``i`` belongs at cell ``perm.index(i)``, the
    inverse of the permutation, and a walk of ``>``/``<`` carries the
    pointer there.  Reading the permutation forward instead puts the right
    bits in the wrong cells and computes a different function.

    **This is not the cheapest build, and the trade is deliberate.**
    Filling in *cell* order -- cell ``c`` taking ``{X perm[c]}`` -- emits no
    walk at all and delivers the full 12.0% screen against the 9.15% here,
    but it puts the placeholders out of name order where every other
    generator in this module emits ``{X0}``..``{Xn-1}`` in sequence.  Both
    are correct, since ``instantiate`` substitutes by *name*, so this is a
    consistency choice costing 2.85 points.  The walk is cheap in absolute
    terms and shows up at all only because Back's programs are small -- 82
    characters on average at n=3, against LaserFuck's 326.

    Keeping the ``-``/``{Xi}`` pairs intact preserves the equal-width
    embedding: the primer and the placeholder are one unit and are never
    separated, so both bits still cost the same two rows and the template's
    height cannot leak an input.
    """
    n = _validate_truth_table(truth_table)

    # The load: fill the input cells, then '>' to open the answer cell at n
    # and walk the pointer back to cell 0 for the tree's first test.  Held as
    # units because a '{Xi}' is one grid cell but four template characters.
    #
    # The load runs the ``{Xi}`` in *name* order and walks the pointer to the
    # cell each one belongs in.  Cell ``c`` is tested by level ``c``, which
    # has to test input ``perm[c]``, so input ``i`` belongs at cell
    # ``perm.index(i)`` -- the inverse of the permutation.
    #
    # Filling in cell order instead (cell ``c`` taking ``{X perm[c]}``) emits
    # no walk at all and is what this generator did briefly: it costs nothing
    # and delivers the full 12.0% screen against the 9.15% here.  It is not
    # kept, because it puts the template's placeholders out of name order,
    # and every other generator in this module emits ``{X0}``..``{Xn-1}`` in
    # sequence.  The saving is real but the exception is not worth it; see
    # the docstring for the trade.
    cells = [0] * n
    for level, i in enumerate(perm):
        cells[i] = level

    def walk(frm: int, to: int) -> list[str]:
        """Move the pointer from cell ``frm`` to cell ``to``, one per row."""
        return [">" if to >= frm else "<"] * abs(to - frm)

    # Emitted in *reverse* name order, because the load is drawn bottom-to-top
    # into column 0 (the beam runs up it), so the template's text reads the
    # units backwards.  Loading input ``n-1`` first therefore puts ``{X0}``
    # first in the emitted template, which is the order every other generator
    # in this module reads in.  The walk costs whatever it costs; the search
    # over input orders prices it either way.
    units: list[str] = []
    at = 0
    for cell in range(n - 1, -1, -1):
        # Two units per input, so neither bit has to be written as a blank:
        # the beam reads one cell per row in column 0, so the setter's second
        # command needs a row of its own rather than the column beside it.
        # Where the tree is the taller of the two these rows already exist.
        #
        # The first row is a constant '-' that primes the cell to 1 for both
        # bits alike, and the *second* carries the placeholder that finishes
        # it: '-' again to flip a zero back down, '+' to leave a one standing.
        # Putting the bit on the trailing row rather than the leading one is
        # what makes every load row execute -- see the fill for why the older
        # '{Xi}' + '+' order skipped a row instead.
        #
        # The walk that puts this input in its cell goes *before* the pair,
        # never between the two halves of it: splitting them would break the
        # equal-width embedding, since the primer and the placeholder have to
        # stay two rows for either bit.
        units.extend(walk(at, cells[cell]))
        units.append("-")
        units.append("{X" + str(cell) + "}")
        at = cells[cell]
    # Open the answer cell at n, then home to cell 0 for the tree's first
    # test.  Under the identity order the last input sits at cell n-1 and
    # this is the single '>' the load always ended on.
    units.extend(walk(at, n))
    units.extend("<" * n)

    # The load occupies column 0 and the tree everything from column 1, so the
    # tree carries no indent for it -- the drawing's width is the tree's alone.
    # A single '/' at the origin performs both turns.  The beam starts at (0,0)
    # heading right; the '/' turns it up, off the top edge and onto the bottom
    # row, where it runs the load *upward* back to the origin; the '/' takes it
    # again, now heading up, and turns it right into the tree.  So the load is
    # written bottom-to-top, and an earlier layout's two '\' -- one to drop the
    # beam off the load's end, one to turn it back right -- are both gone along
    # with the row and the indent they cost.
    #
    # Riding off the top edge makes the grid's toroidal wrap required:
    # ``_Machine.step`` advances with ``% len(code)``, so up from row 0 lands
    # on the last row.  The wiki text the interpreter quotes does not mention
    # the edges at all, and no interpreter test covers a wrap, so this is the
    # one place the generator leans on behaviour with no witness outside this
    # repo's own interpreter.
    grid: dict[tuple[int, int], str] = {}
    next_row = [1]
    constant = constant_span_test(truth_table)

    def leaf(level: int, value: str, row: int, col: int) -> None:
        # walk to the single answer cell, write a 1 there when the leaf's
        # value is 1 (it starts 0), and halt
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

    # The grid is as tall as whichever of the two needs more rows: the tree
    # wants 2**n and the load wants one row per unit below the '/'.  Past
    # n = 3 the tree is the taller, so the load's rows start sharing with tree
    # rows -- safe for the same reason the whole template is: a '{Xi}' is the
    # only thing on its row that instantiation resizes, it always shrinks by
    # exactly three (every embedding is one character, for either bit value),
    # and it sits left of the tree, so the tree glyphs on that row slide back
    # to the columns they were drawn for.  An embedding whose width depended
    # on the bit would break that silently.
    height = max(max(r for r, _ in grid) + 1, 1 + len(units))
    width = max(c for _, c in grid) + 1
    rows = [[" "] * width for _ in range(height)]
    for (r, c), ch in grid.items():
        rows[r][c] = ch
    rows[0][0] = "/"
    for k, unit in enumerate(units):
        rows[height - 1 - k][0] = unit
    # Every row is built at the full grid width, so the rstrip trims the pad
    # each one carries past its last glyph.  It no longer has a bit to hide:
    # both bits embed as a single command ('-' or '+'), never as the blank a
    # zero once used, so no placeholder row instantiates to whitespace and
    # the strip cannot change a filled row's length.
    return _reflect_back("\n".join("".join(row).rstrip() for row in rows))
