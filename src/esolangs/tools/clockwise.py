"""Boolean-function generator for Clockwise."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
)

# Cells in a Clockwise leaf: 'S', the seven ';' that print the answer digit
# with the '+' that set their parity, and the 'S+?' exit.  Both digits fit
# in this height -- '0' pads with one extra 'S' -- so the two leaves of a
# node always end on the same row.
_CLOCKWISE_LEAF = 14


# Rows one level of the tree spends: 'S', seven '.', and the '?' that turns.
_CLOCKWISE_LEVEL = 9


def clockwise(truth_table: str, width: int | None = None) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints the result as the ASCII digit ``'0'`` or ``'1'``.
    Without a width, the compact form compares the flat tree with one partial
    stack bounded to eight columns per input and keeps the shorter.  This is
    two named linear builds, not a search over stack depths.  ``width`` asks
    for a column count; the tree stacks as much of itself as it needs to meet
    one, and a width under the floor returns the narrowest program rather than
    refusing.

    The program is a decision tree in a closed ring.  ``S`` zeroes the
    accumulator and seven ``.`` reads consume a ``0``/``1`` input char's seven
    bits, leaving its value bit in the accumulator.  At each node a ``?``
    turns the pointer by ``acc`` quarter-turns, so a zero bit continues down
    the spine while a one bit turns aside into a column of its own; three
    ``R`` in an L pattern turn it back down into that column.

    A leaf prints the answer's seven bits with ``;``, which emits ``acc % 2``,
    so a ``+`` before a ``;`` flips the parity into the bit that position
    needs.  Printing the ASCII digit rather than the bare bit costs almost
    nothing here: ``'0'`` is ``0110000`` and ``'1'`` is ``0110001``, so the
    two leaves differ by a single ``+``.  The leaf then resets and counts up
    to one (``S+``) so the exit ``?`` sees ``acc == 1`` whatever it printed,
    and turns left along its own row; an ``S`` just left of each exit drops
    passing paths back to zero so they do not turn on another leaf's exit.

    Every exit row ends at column 0 on a ``!``, which turns a path that
    arrives with a zero accumulator up the left edge, and a ``+`` one row
    above puts the accumulator back to one -- so a path climbing the edge
    passes the exits above it without turning on their ``!``.  That is what
    lets leaves finish on *different* rows: the ring closes through column 0
    rather than through one shared bottom row.

    Three ways the tree composes its paths.  A node can send its one-branch
    to a column of its own, which
    costs the columns that branch displaces -- the classic layout, and the
    reason an unstacked tree grows as ``2 ** (n + 1)``.  Or it can send it
    one column left and *stack* the two subtrees, the zero-branch falling
    down its own column through the one-branch's rows to start below them.
    Stacking costs one column per level instead of ``2 ** (n - bit)``, and
    pays for it in rows: the subtree below a stacked node is written twice
    over, so each stacked level doubles the program's height.

    Wide default tables alternate those two compositions by level.  Across
    each pair of levels both width and height only double, so each is
    O(sqrt(T)) and the rendered rectangle is O(T).  The builder visits the
    O(T) tree cells and that rectangle once, so generation time is O(T) too.
    Explicit widths retain the prefix-stacked layout below.

    The shallow levels displace furthest, so those are the ones stacked
    first: ``width`` fixes the smallest number of levels that brings the
    grid inside it, and the rest of the tree lays out flat.

    A subtree whose rows all agree stops branching, which narrows the ring:
    a node displaces only as far as its zero-branch actually spans, and a
    folded node spans one column.

    Two things the fold does *not* get to do.  It cannot drop the reads:
    Clockwise reads inside the tree, seven ``.`` per level, so a folded
    column still spends them (and an ``S`` where the ``?`` would have been,
    keeping the two leaves of a node the same height).  And it cannot narrow
    past the hoist: the root's seven reads sit on row 0 left of the corner
    ``R``, which retires seven rows but needs seven free columns, so an
    unasked-for width floors at what the hoist needs.  A width that is
    asked for may go under it -- the request is the point.
    """
    n = _validate_truth_table(truth_table)
    alternating = width is None and n > 4
    constant_span = constant_span_test(truth_table)

    def stacks(bit: int, stacked: int) -> bool:
        """Whether this level composes its children vertically."""
        return bit % 2 == 0 if alternating else bit < stacked

    def constant(bit: int, combo: int) -> bool:
        """Whether every row this subtree covers agrees.

        Rows split most-significant-first, so the subtree entered at
        ``bit`` with prefix ``combo`` covers the contiguous run of
        ``2 ** (n - bit)`` rows starting at ``combo << (n - bit)``.

        Alternating composition keeps the complete tree.  Its per-level
        width/height proof already gives O(T), while folding makes sibling
        heights unequal and can open the outer ring.
        """
        if alternating:
            return False
        span = 2 ** (n - bit)
        start = combo << (n - bit)
        return constant_span(start, start + span)

    def leafy(bit: int, combo: int) -> bool:
        """Whether this subtree stops here, either at ``n`` or on a fold."""
        return bit == n or (bit > 0 and constant(bit, combo))

    shapes: dict[tuple[int, int, int], tuple[int, int]] = {}

    def shape(bit: int, combo: int, stacked: int) -> tuple[int, int]:
        """Report the columns and rows this subtree needs, spine on the right.

        A leaf, folded or not, is one column: a folded one pads its skipped
        levels to the rows they would have spent, so the two subtrees of a
        node are always the same height and their leaves share a row.

        A stacked node spans one more column than its one-branch (or the
        three its own turn needs, whichever is wider) and as many rows as
        both subtrees together.  A flat one displaces its one-branch clear
        of the zero-branch's span -- two columns at the least, so no leaf
        sits directly left of another and the ``S`` before an exit has a
        cell of its own -- and the two subtrees share the rows.
        """
        key = (bit, combo, stacked)
        if key not in shapes:
            if leafy(bit, combo):
                shapes[key] = (1, _CLOCKWISE_LEVEL * (n - bit) + _CLOCKWISE_LEAF)
            else:
                one = shape(bit + 1, (combo << 1) | 1, stacked)
                zero = shape(bit + 1, combo << 1, stacked)
                if stacks(bit, stacked):
                    shapes[key] = (
                        max(3, one[0] + 1, zero[0]),
                        _CLOCKWISE_LEVEL + one[1] + zero[1],
                    )
                else:
                    step = max(2, zero[0])
                    shapes[key] = (
                        step + max(1, one[0] - 1) + 1,
                        _CLOCKWISE_LEVEL + max(one[1], zero[1]),
                    )
        return shapes[key]

    def spine(stacked: int) -> int:
        """Return the root's column with ``stacked`` levels stacked.

        Column 0 belongs to the ring, so the tree starts one column in.
        The hoist needs seven free columns left of the root and pays for
        them with seven rows, which is the better trade whenever the width
        was not asked for.
        """
        root = shape(0, 0, stacked)[0]
        if 2 ** (n + 1) >= 8 and (width is None or width >= 9):
            root = max(root, 8)
        return root

    # The shallow levels are the expensive ones -- a node at ``bit``
    # displaces ``2 ** (n - bit)`` columns -- so stacking starts at the
    # root and takes as few levels as the width needs.  A width under the
    # floor stacks everything, which is the narrowest tree there is.
    stacked = 0
    if width is not None:
        for count in range(n + 1):
            stacked = count
            if spine(count) + 1 <= width:
                break

    root = spine(stacked)
    # What the hoist's floor added over the tree's own span.  The turns are
    # relative, so the tree's absolute column never matters -- but its rows
    # are trimmed, so a cell further right costs a character.  Spending the
    # slack on the root's own displacement slides the whole one-branch back
    # against the left edge and leaves the gap between the two subtrees,
    # where the zero-branch's columns already set every row's length.
    slack = root - shape(0, 0, stacked)[0]
    hoist = root >= 8
    # Hoisting the root's reads onto row 0 retires seven rows of spine, so
    # the tree starts that much higher and every row below rides up with it.
    shift = 7 if hoist else 0

    cells: dict[tuple[int, int], str] = {}
    exits: list[tuple[int, int]] = []

    def place(node: tuple[int, int], ch: str) -> None:
        """Write ``ch`` at ``node``, refusing to land on an occupied cell.

        The geometry above is what keeps two cells apart; this is what
        says so.  A Clockwise cell acts only on the pointer standing on it,
        so an overwrite is the whole of what a bad layout can do to the
        grid -- and a program that silently lost a turn would be wrong in a
        way only a run of every input combination would find.
        """
        if node in cells:
            raise AssertionError(f"two cells at {node}: {cells[node]!r} and {ch!r}")
        cells[node] = ch

    def leaf(x: int, y: int, combo: int) -> None:
        """Print the answer at ``(x, y)`` and leave by the row it ends on."""
        # Emit the answer as the ASCII digit rather than as the raw bit.
        # Seven ';' print one bit each, most significant first, and each
        # prints acc % 2 -- so a '+' before a ';' is what flips the parity
        # into the bit that position needs.  '0' is 0110000 and '1' is
        # 0110001, which differ only in the last bit, so the two leaves are
        # the same shape apart from one '+'.
        result = int(truth_table[combo])
        code = "S"
        acc = 0
        for bit in format(_ASCII_ZERO + result, "07b"):
            if acc % 2 != int(bit):
                code += "+"
                acc += 1
            code += ";"
        # A '?' turns by acc quarter-turns and must see exactly 1 to turn
        # left onto its exit row.  The accumulator is 2 or 3 by now
        # depending on the digit, so reset and count up to 1 rather than
        # tracking it: 'S+' is uniform where a bare '+' would not be.  The
        # extra 'S' pads the shorter leaf so both are _CLOCKWISE_LEAF cells,
        # which is what keeps the two leaves of a node the same height.
        code += "S" * (_CLOCKWISE_LEAF - len(code) - 2) + "+?"
        for i, ch in enumerate(code):
            place((x, y + i), ch)
        exits.append((x, y + _CLOCKWISE_LEAF - 1))

    def build(bit: int, x: int, y: int, combo: int) -> None:
        """Lay the subtree for ``combo`` at ``bit``, spine head at ``(x, y)``."""
        if leafy(bit, combo):
            # Every row below here agrees, so the remaining bits cannot
            # change the answer and this column needs no more branching.
            # The reads are not optional, though: a program whose input
            # count depended on its table would desync a caller feeding
            # several from one stream, and unlike the tape generators
            # clockwise reads *inside* the tree.  So the skipped levels
            # still spend their ``S`` and seven ``.`` -- everything but
            # the ``?`` that would have turned the pointer.  The ninth row
            # is padded with an ``S`` -- a no-op on an accumulator the
            # reads leave at 0 or 1 -- so the column still ends where an
            # unfolded one would, and a node's two leaves stay level.
            for level in range(n - bit):
                place((x, y + _CLOCKWISE_LEVEL * level), "S")
                for i in range(7):
                    place((x, y + _CLOCKWISE_LEVEL * level + 1 + i), ".")
                place((x, y + _CLOCKWISE_LEVEL * level + 8), "S")
            leaf(x, y + _CLOCKWISE_LEVEL * (n - bit), combo << (n - bit))
            return
        if bit == 0 and hoist:
            # The seven reads sit on row 0, left of the corner ``R``; the
            # node's ``?`` is all that is left of its spine.
            for i in range(7):
                place((x - 7 + i, 0), ".")
        else:
            place((x, y), "S")
            for i in range(7):
                place((x, y + 1 + i), ".")
        place((x, y + 8), "?")
        one = shape(bit + 1, (combo << 1) | 1, stacked)
        zero = shape(bit + 1, combo << 1, stacked)
        # A stacked node displaces a single column and drops its
        # zero-branch below the one-branch's rows; a flat one displaces
        # past the zero-branch's span and the two share the rows.
        step = 1 if stacks(bit, stacked) else max(2, zero[0])
        xn = x - step - (slack if bit == 0 else 0)
        # b=1: '?' turns the pointer aside, then three R's turn it down
        place((xn, y + 8), " ")
        place((xn - 1, y + 8), "R")
        place((xn - 1, y + 7), "R")
        place((xn, y + 7), "R")
        build(bit + 1, xn, y + 9, (combo << 1) | 1)
        below = one[1] if stacks(bit, stacked) else 0
        # b=0: fall down this column, past the one-branch when it stacks
        build(bit + 1, x, y + 9 + below, combo << 1)

    build(0, root, 1 - shift, 0)

    for x, y in exits:
        # Drop a passing path back to zero so it does not turn on the exit
        # of a leaf further left along the same row.
        place((x - 1, y), "S")
    for y in sorted({y for _, y in exits}):
        # The ring closes up column 0: '!' takes a path that arrives with a
        # zero accumulator, and the '+' above it puts the accumulator back
        # so the climb passes every exit above without turning.
        place((0, y), "!")
        place((0, y - 1), "+")
    place((root, 0), "R")

    height = max(y for _, y in cells) + 1
    span = max(x for x, _ in cells) + 1
    grid = [[" "] * span for _ in range(height)]
    for (x, y), ch in cells.items():
        # ``span`` and ``height`` are derived from these very cells, so the
        # test holds for every one of them; it stays as the guard that keeps
        # a future caller's stray coordinate from writing outside the grid.
        if 0 <= x < span and 0 <= y < height:  # pragma: no branch - see above
            grid[y][x] = ch
    # The grid is a fixed-size rectangle of blanks that the cells are painted
    # into, so a row's trailing filler is never reached; the interpreter pads
    # short rows itself, so trimming it changes nothing but the file.
    program = "\n".join("".join(row).rstrip() for row in grid)
    if width is None and not alternating:
        partially_stacked = clockwise(truth_table, width=8 * n)
        return min((program, partially_stacked), key=len)
    return program
