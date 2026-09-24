"""Boolean-function generator for Clockwise."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
)

# Rows a leaf spends: ten for the digit (seven ';' and the three '+' the
# worst parity costs), then the two exit rows a pair shares.
_CLOCKWISE_LEAF = 13

# Where the upper of a leaf's two exit rows sits.  A pair's one-branch turns
# there and holds 'S' two rows down; its zero-branch does the reverse, so each
# zeroes the other's escaping accumulator without a column of its own.
_CLOCKWISE_UPPER = 10


# Rows one level spends: seven '.' and the '?' that turns.  A read clears
# the accumulator's low bit, so the 0 or 1 a node inherits needs no ``S``.
_CLOCKWISE_LEVEL = 8

# Columns a turn gadget spends when it carries a child's reads: the turn
# around, the seven ``.`` on the way back, and the corner that turns down.
_CLOCKWISE_GADGET = 9


def clockwise(truth_table: str, width: int | None = None) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    program prints ``'0'`` or ``'1'``.  Without ``width`` the flat tree is
    compared with one partial stack bounded to eight columns per input;
    ``width`` stacks as many levels as needed, and a width under the floor
    returns the narrowest program.

    A decision tree in a closed ring.  Seven ``.`` reads leave the input's
    value bit, each clearing the accumulator's low bit first, so a node
    needs no ``S`` to clear the 0 or 1 it inherits; at each node ``?`` turns
    by ``acc`` quarter-turns, so a zero continues down the spine and a one
    turns into its own column.  A leaf prints seven bits with ``;`` (``+``
    flips a bit's parity) and leaves on the ``+`` a digit always spends,
    which the exit ``?`` reads as nonzero.  Every exit row ends at a ``!``
    on column 0 that turns a zero accumulator up the left edge, with ``+``
    above it, so leaves finish on different rows.

    Reads laid down a column cost seven rows; laid along a row they cost
    only columns, and the turn gadget already walks a row.  So a node whose
    one-branch has nine columns of gap spends them on a wider gadget and
    reads its child's seven bits on the way back, leaving the child its
    ``?`` alone.  That pays where siblings stack and their rows add.

    A node can send its one-branch to its own column or one column left and
    *stack* the subtrees (one column per level, doubling the height).  Wide
    default tables alternate the two per level, so width and height are each
    O(sqrt(T)) and the rectangle O(T); explicit widths stack the shallowest
    levels first.  A constant subtree narrows the ring but keeps its seven
    reads per level and cannot narrow past the hoist (seven free columns for
    the root's reads) unless asked.
    """
    n = _validate_truth_table(truth_table)
    alternating = width is None and n > 4
    constant_span = constant_span_test(truth_table)

    def stacks(bit: int, stacked: int) -> bool:
        """Whether this level composes its children vertically.

        Alternating from the bottom -- the last two levels and the root
        flat -- beats every other schedule searched to ``n == 14``.
        """
        if not alternating:
            return bit < stacked
        return 0 < bit <= n - 3 and (n - bit) % 2 == 1

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

    def paired(bit: int, combo: int, stacked: int) -> bool:
        """Whether this node's children are two leaves that guard each other."""
        if stacks(bit, stacked) or leafy(bit, combo):
            return False
        return leafy(bit + 1, combo << 1) and leafy(bit + 1, (combo << 1) | 1)

    def gap(bit: int, combo: int, stacked: int) -> int:
        """Return the columns between this node's spine and its one-branch."""
        if stacks(bit, stacked) or paired(bit, combo, stacked):
            return 1
        return max(2, shape(bit + 1, combo << 1, stacked, hoisted=False)[0])

    shapes: dict[tuple[int, int, int, bool], tuple[int, int]] = {}
    hoists: dict[tuple[int, int, int, bool], bool] = {}

    def shape(bit: int, combo: int, stacked: int, *, hoisted: bool) -> tuple[int, int]:
        """Report the columns and rows this subtree needs, spine on the right.

        A leaf is one column, padded to its skipped rows so siblings share a
        row.  Stacked: one more column than the one-branch, rows of both.
        ``hoisted`` means the parent's turn gadget already read this node's
        seven bits, so the node is its ``?`` alone rather than eight rows.
        """
        key = (bit, combo, stacked, hoisted)
        if key not in shapes:
            if leafy(bit, combo):
                shapes[key] = (1, _CLOCKWISE_LEVEL * (n - bit) + _CLOCKWISE_LEAF)
                return shapes[key]
            own = 1 if hoisted else _CLOCKWISE_LEVEL
            best: tuple[int, int] | None = None
            choice = False
            for hoist_one in (False, True):
                step = gap(bit, combo, stacked)
                # A hoisted child's own turn gadget shares the row this
                # node's left leg runs along, so it has to sit past the
                # corner that leg turns at -- a whole gadget to the left.
                if hoist_one and (
                    leafy(bit + 1, (combo << 1) | 1)
                    or gap(bit + 1, (combo << 1) | 1, stacked) < _CLOCKWISE_GADGET
                ):
                    continue
                one = shape(bit + 1, (combo << 1) | 1, stacked, hoisted=hoist_one)
                zero = shape(bit + 1, combo << 1, stacked, hoisted=False)
                # The read run overhangs the one-branch by a gadget's width.
                wide = max(one[0], _CLOCKWISE_GADGET) if hoist_one else one[0]
                if stacks(bit, stacked):
                    cand = (
                        max(3, wide + 1, zero[0]),
                        own + one[1] + zero[1],
                    )
                else:
                    # A pair guards itself, so the one-branch needs no gap.
                    cand = (
                        step + max(1, wide - 1) + 1,
                        own + max(one[1], zero[1]),
                    )
                if best is None or cand[0] * cand[1] < best[0] * best[1]:
                    best, choice = cand, hoist_one
            assert best is not None  # ``hoist_one`` false is always allowed.
            shapes[key] = best
            hoists[key] = choice
        return shapes[key]

    def spine(stacked: int) -> int:
        """Return the root's column with ``stacked`` levels stacked.

        Column 0 is the ring's; the hoist trades seven columns for seven rows.
        """
        root = shape(0, 0, stacked, hoisted=True)[0]
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
    hoist = root >= 8
    # Spend the hoist's slack on the root's displacement, so the gap lands
    # where the zero-branch already sets row lengths.
    base = shape(0, 0, stacked, hoisted=hoist)[0]
    root = max(root, base)
    slack = root - base

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

    def leaf(x: int, y: int, combo: int, drop: int) -> None:
        """Print the answer at ``(x, y)``, ``drop`` rows below the upper exit.

        The accumulator arrives even, so a digit costs three '+' at most.
        """
        # Seven ';' print acc % 2 each, MSB first; '+' flips the parity.
        result = int(truth_table[combo])
        code = ""
        acc = 0
        for bit in format(_ASCII_ZERO + result, "07b"):
            if acc % 2 != int(bit):
                code += "+"
                acc += 1
            code += ";"
        # An exit '?' turns on any nonzero accumulator, which the digit's
        # own '+' leave; the lower exit rebuilds one past its guarding 'S'.
        code += " " * (_CLOCKWISE_UPPER - len(code))
        code += "? S" if drop == 0 else "S+?"
        for i, ch in enumerate(code):
            if ch != " ":
                place((x, y + i), ch)
        exits.append((x, y + _CLOCKWISE_UPPER + drop))

    def build(
        bit: int,
        x: int,
        y: int,
        combo: int,
        drop: int = 2,
        *,
        hoisted: bool = False,
    ) -> None:
        """Lay the subtree for ``combo`` at ``bit``, spine head at ``(x, y)``.

        ``drop`` is 0 for the one-branch of a pair, which exits two rows up.
        ``hoisted`` means the reads are already on the row above, so ``y`` is
        the ``?``'s own row rather than the first of seven ``.``.
        """
        if leafy(bit, combo):
            # Folded: the skipped levels still spend seven ``.`` (Clockwise
            # reads inside the tree), with an ``S`` where the ``?`` was so
            # the column ends where an unfolded one would.
            for level in range(n - bit):
                for i in range(7):
                    place((x, y + _CLOCKWISE_LEVEL * level + i), ".")
                place((x, y + _CLOCKWISE_LEVEL * level + 7), "S")
            leaf(x, y + _CLOCKWISE_LEVEL * (n - bit), combo << (n - bit), drop)
            return
        if bit == 0 and hoisted:
            # The seven reads sit on row 0, left of the corner ``R``; the
            # node's ``?`` is all that is left of its spine.
            for i in range(7):
                place((x - 7 + i, 0), ".")
        elif not hoisted:
            for i in range(7):
                place((x, y + i), ".")
        turn = y if hoisted else y + 7
        place((x, turn), "?")
        lift = hoists[(bit, combo, stacked, hoisted)]
        one = shape(bit + 1, (combo << 1) | 1, stacked, hoisted=lift)
        zero = shape(bit + 1, combo << 1, stacked, hoisted=False)
        # Stacked: one column, zero-branch below; flat: past the span, shared rows.
        pair = paired(bit, combo, stacked)
        step = 1 if stacks(bit, stacked) or pair else max(2, zero[0])
        xn = x - step - (slack if bit == 0 else 0)
        # b=1: '?' turns the pointer aside, then three R's turn it down; the
        # corner's 'S', crossed twice, hands the child an even accumulator.
        if lift:
            # The child's seven reads ride the way back: 'S' clears the
            # accumulator on the way out (off the column the return turns
            # down, which would clear the bit just read), the far corner
            # turns up and back, and the reads land before the last corner.
            back = xn - _CLOCKWISE_GADGET + 1
            place((xn - 1, turn), "S")
            place((back, turn), "R")
            place((back, turn - 1), "R")
            for i in range(7):
                place((back + 1 + i, turn - 1), ".")
            place((xn, turn - 1), "R")
        else:
            place((xn, turn), "S")
            place((xn - 1, turn), "R")
            place((xn - 1, turn - 1), "R")
            place((xn, turn - 1), "R")
        build(bit + 1, xn, turn + 1, (combo << 1) | 1, 0 if pair else 2, hoisted=lift)
        below = one[1] if stacks(bit, stacked) else 0
        # b=0: fall down this column, past the one-branch when it stacks
        build(bit + 1, x, turn + 1 + below, combo << 1)

    build(0, root, 2 if hoist else 1, 0, 2, hoisted=hoist)

    for x, y in exits:
        # Drop a passing path to zero so it does not turn on a leaf's exit.
        # A pair's zero-branch already has its sibling's 'S' to the left.
        if (x - 1, y) not in cells:
            place((x - 1, y), "S")
        if cells[(x - 1, y)] != "S":
            raise AssertionError(f"exit at {(x, y)} is not guarded")
    for y in {y for _, y in exits}:
        # The ring closes up column 0: '!' turns a zero accumulator up,
        # the '+' above restores it past every exit.  ``place`` refuses a
        # collision, so the order is immaterial and the set is not sorted.
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
