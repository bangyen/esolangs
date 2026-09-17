"""Boolean-function generator for Clockwise."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
)

# Cells in a leaf: 'S', seven ';' with their '+', and the 'S+?' exit;
# '0' pads with one 'S' so both leaves of a node end on the same row.
_CLOCKWISE_LEAF = 14


# Rows one level of the tree spends: 'S', seven '.', and the '?' that turns.
_CLOCKWISE_LEVEL = 9


def clockwise(truth_table: str, width: int | None = None) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    program prints ``'0'`` or ``'1'``.  Without ``width`` the flat tree is
    compared with one partial stack bounded to eight columns per input;
    ``width`` stacks as many levels as needed, and a width under the floor
    returns the narrowest program.

    A decision tree in a closed ring.  ``S`` zeroes the accumulator, seven
    ``.`` reads leave the input's value bit; at each node ``?`` turns by
    ``acc`` quarter-turns, so a zero continues down the spine and a one
    turns into its own column.  A leaf prints seven bits with ``;`` (``+``
    flips a bit's parity; ``'0'`` and ``'1'`` differ by one ``+``), then
    ``S+`` so the exit ``?`` sees 1.  Every exit row ends at a ``!`` on
    column 0 that turns a zero accumulator up the left edge, with ``+`` above
    it, so leaves finish on different rows.

    A node can send its one-branch to its own column (width ``2 ** (n + 1)``
    unstacked) or one column left and *stack* the subtrees (one column per
    level, doubling the height).  Wide default tables alternate the two per
    level, so width and height are each O(sqrt(T)) and the rectangle O(T);
    explicit widths stack the shallowest levels first.  A constant subtree
    narrows the ring but keeps its seven reads per level and cannot narrow
    past the hoist (seven free columns for the root's reads) unless asked.
    """
    n = _validate_truth_table(truth_table)
    alternating = width is None and n > 4
    constant_span = constant_span_test(truth_table)

    def stacks(bit: int, stacked: int) -> bool:
        """Whether this level composes its children vertically."""
        return bit % 2 == 0 if alternating else bit < stacked

    def constant(bit: int, combo: int) -> bool:
        """Whether every row this subtree covers agrees.

        Alternating composition keeps the complete tree: folding makes sibling
        heights unequal and can open the ring.
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

        A leaf is one column, padded to its skipped rows so siblings share a
        row.  Stacked: one more column than the one-branch, rows of both.  Flat:
        the one-branch clear of the zero-branch's span (two columns at least).
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

        Column 0 is the ring's; the hoist trades seven columns for seven rows.
        """
        root = shape(0, 0, stacked)[0]
        if 2 ** (n + 1) >= 8 and (width is None or width >= 9):
            root = max(root, 8)
        return root

    # A node at ``bit`` displaces ``2 ** (n - bit)`` columns, so stack from
    # the root, as few levels as the width needs.
    stacked = 0
    if width is not None:
        for count in range(n + 1):
            stacked = count
            if spine(count) + 1 <= width:
                break

    root = spine(stacked)
    # Spend the hoist's slack on the root's displacement, so the gap lands
    # between the subtrees where the zero-branch already sets row lengths.
    slack = root - shape(0, 0, stacked)[0]
    hoist = root >= 8
    # Hoisting the root's reads onto row 0 retires seven rows of spine.
    shift = 7 if hoist else 0

    cells: dict[tuple[int, int], str] = {}
    exits: list[tuple[int, int]] = []

    def place(node: tuple[int, int], ch: str) -> None:
        """Write ``ch`` at ``node``, refusing to land on an occupied cell.

        An overwrite is the whole of what a bad layout can do, and would only
        show under a run of every input.
        """
        if node in cells:
            raise AssertionError(f"two cells at {node}: {cells[node]!r} and {ch!r}")
        cells[node] = ch

    def leaf(x: int, y: int, combo: int) -> None:
        """Print the answer at ``(x, y)`` and leave by the row it ends on."""
        # Seven ';' print acc % 2 each, MSB first; '+' flips the parity.
        result = int(truth_table[combo])
        code = "S"
        acc = 0
        for bit in format(_ASCII_ZERO + result, "07b"):
            if acc % 2 != int(bit):
                code += "+"
                acc += 1
            code += ";"
        # The exit '?' must see exactly 1: 'S+' resets rather than tracks
        # the 2 or 3 the digit left, and the extra 'S' pads the shorter leaf.
        code += "S" * (_CLOCKWISE_LEAF - len(code) - 2) + "+?"
        for i, ch in enumerate(code):
            place((x, y + i), ch)
        exits.append((x, y + _CLOCKWISE_LEAF - 1))

    def build(bit: int, x: int, y: int, combo: int) -> None:
        """Lay the subtree for ``combo`` at ``bit``, spine head at ``(x, y)``."""
        if leafy(bit, combo):
            # Folded: the skipped levels still spend ``S`` and seven ``.``
            # (Clockwise reads inside the tree), with an ``S`` where the
            # ``?`` was so the column ends where an unfolded one would.
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
        # Stacked: one column, zero-branch below; flat: past the span, shared rows.
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
        # Drop a passing path to zero so it does not turn on a leaf's exit.
        place((x - 1, y), "S")
    for y in sorted({y for _, y in exits}):
        # The ring closes up column 0: '!' turns a zero accumulator up,
        # the '+' above restores it past every exit.
        place((0, y), "!")
        place((0, y - 1), "+")
    place((root, 0), "R")

    height = max(y for _, y in cells) + 1
    span = max(x for x, _ in cells) + 1
    grid = [[" "] * span for _ in range(height)]
    for (x, y), ch in cells.items():
        # Always holds; guards a future stray coordinate.
        if 0 <= x < span and 0 <= y < height:  # pragma: no branch - see above
            grid[y][x] = ch
    # Trailing filler is never reached and the interpreter pads short rows.
    program = "\n".join("".join(row).rstrip() for row in grid)
    if width is None and not alternating:
        partially_stacked = clockwise(truth_table, width=8 * n)
        return min((program, partially_stacked), key=len)
    return program
