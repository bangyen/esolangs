"""Boolean-function generator for ArrowQueue, and the tree it draws."""

from esolangs.tools.helpers import _validate_truth_table

# --- ArrowQueue (no-input grid language; parameterized + termination convention) ---
#
# Boolean generator for ArrowQueue.
#
# ArrowQueue is a 2D grid language with a queue: ``*`` turns the pointer
# clockwise, ``~`` pushes the current direction onto the queue, and ``+``
# pops the queue and points the pointer in the popped direction (halting on
# an empty pop).  It has no input and no output, so the generator follows
# the parameterized convention (like ``bitdeque``/``minsky_swap``) AND the
# termination convention (like ``point_break``): the template carries
# ``{Xi}`` placeholders for the input bits, :func:`_instantiate_arrowqueue`
# fills each with the language's per-bit embedding, and the result is read
# from whether the instantiated program *halts* (a ``0`` table entry) or
# *loops forever* (a ``1`` entry) -- the same convention as the committed
# halt-vs-hang ring (see ``the limitations ledger``).
#
# The template is a grid:
#
# - the first rows embed each input once, one ``{Xi}`` placeholder per bit
#   (the queue stores bits as directions: right is 0, down is 1);
# - the next rows queue the right/down/left/up loop components (a ``0``
#   leaf pops them all and then halts on the empty pop; a ``1`` leaf's ring
#   sustains on them);
# - the decision tree then pops each bit at a ``+`` branch and routes the
#   pointer right for a 0 bit or down for a 1 bit.  A ``0`` leaf is empty,
#   so the pointer runs off the grid and halts; a ``1`` leaf is a ring that
#   pushes on every edge and pops on every corner, sustaining forever.
#
# Wide tables replace that tree with a marker count.  Input ``i`` appends
# either zero or ``2**(n-1-i)`` down headings; a right sentinel and the four
# ring headings follow.  A vertical chain pops one marker per table row, so
# the sentinel turns right at exactly the indexed row.  A zero row runs out
# of the grid, while a one row enters the same sustaining ring as above.  The
# marker arms have lengths ``1, 2, 4, ..., T/2``, whose geometric sum is
# ``T-1`` -- not the quadratic sum of every integer through ``T/2``.
#
# The tree is a full binary tree built from 3x3 blocks: a 0-branch
# (``" + "``) pops the next bit, sending the pointer right for 0 and down
# for 1; a 1-branch (``"*  "``/``"** "``) reflects the down-route back to
# the right; and each leaf is a 3x3 output block.  Connecting two subtrees
# places a 0-branch at the top-left, the first subtree at its right exit,
# the second at the 1-branch's right exit, and the 1-branch at the bottom
# left (one row below the first subtree), filling the rest with spaces.
# The pointer enters the whole tree by descending column 1 from the loop
# section, which pops the top-left 0-branch's ``+`` directly.

_TREE_1 = ["+~+", "~ ~", "+~+"]  # the ``1`` leaf: a self-sustaining ring


_TREE_0 = ["   ", "   ", "   "]  # the ``0`` leaf: empty, runs off-grid to halt


_TREE_BRANCH_0 = [" + ", "   ", "   "]  # pops a bit; 0 goes right, 1 goes down


_TREE_BRANCH_1 = ["*  ", "** ", "   "]  # reflects the down-route back to the right


# Input-embedding blocks.  A ``1`` bit pushes down (1) and a ``0`` bit pushes
# right (0).  The first block is one row taller: the pointer enters it
# heading right from the top-left corner and the ``*`` turns it down onto
# the ``~``, while every later block is entered heading down from the
# previous block's exit (each block leaves the pointer heading down at
# column 3, one row below itself).
# The one blocks carry **inert walls** so each block's glyphs occupy the same
# number of characters as the zero block it stands against -- without them the
# emitted program's length counts the one bits, breaking the equal-width rule.
# A wall is only inert where the IP cannot reach it, which is why the first
# block's row 0 carries none.  See
# ``the relevant generator tests`` for the leak that forced this and why one
# wall per row suffices.
# Every cell a block spells is a glyph: ``.`` is a no-op to the interpreter
# (any character but ``*``, ``~`` and ``+`` is), so the corridor the IP
# walks and the cells it never reaches are written rather than left blank,
# and a bit is never spelled as nothing.  Rows are still stripped of their
# trailing blanks, so a corridor cell past a row's last glyph stays implicit
# and the two blocks' character counts stay equal (fourteen each).
_FIRST_ONE = ["...*", "...~*", "..*", "..*", "..*"]


_FIRST_ZERO = ["...*", "*~* ", "*..*", "*..*", "*.* "]


_NEXT_ONE = ["...~*", "..*", "..*", "..*"]


_NEXT_ZERO = ["*~* ", "*..*", "*..*", "*.* "]


# The loop-component section: entered heading down at column 3 from the last
# embedding block, it queues right, down, left, and up (in that order, so
# the queue holds ``[bits..., R, D, L, U]`` at the tree) and routes the
# pointer down column 1 into the tree.
_MIDDLE = ["*~* ", "*  *", "*  *", "~ ~ ", "*~* ", "**  ", "*  *"]


def _header_rows(bits: list[int]) -> list[str]:
    """Build the input-embedding rows for ``bits`` (most significant first)."""
    rows = list(_FIRST_ONE if bits[0] else _FIRST_ZERO)
    for bit in bits[1:]:
        rows.extend(_NEXT_ONE if bit else _NEXT_ZERO)
    return rows


def _connect(t0: list[str], t1: list[str]) -> list[str]:
    """Connect two decision subtrees into one.

    Places a 0-branch at the top-left, ``t0`` at its right exit, a 1-branch
    at the bottom left (just below ``t0``, catching the down-route), and
    ``t1`` at the 1-branch's right exit; everything else is spaces.
    """
    yb = len(t0)  # the 1-branch's top row: one row below ``t0``
    width = max(3 + len(t0[0]), 3 + len(t1[0]))
    height = max(3, yb + 3, yb + len(t1))
    grid = [[" "] * width for _ in range(height)]
    for r, line in enumerate(_TREE_BRANCH_0):
        for c, ch in enumerate(line):
            grid[r][c] = ch
    for r, line in enumerate(_TREE_BRANCH_1):
        for c, ch in enumerate(line):
            grid[yb + r][c] = ch
    for r, line in enumerate(t0):
        for c, ch in enumerate(line):
            grid[r][3 + c] = ch
    for r, line in enumerate(t1):
        for c, ch in enumerate(line):
            grid[yb + r][3 + c] = ch
    return ["".join(row) for row in grid]


def _drained_leaf(value: str, skipped: int) -> list[str]:
    """Build a folded leaf that drains the ``skipped`` bits it never popped.

    Folding a constant subtree skips its ``+`` branches, which would leave
    those bits queued *ahead* of the four loop components.  A ``0`` leaf
    does not care -- it halts by running off the grid, and no queue content
    prevents that -- but a ``1`` leaf's ring pops a direction at each corner
    and needs to find exactly ``R, D, L, U``.

    So each skipped bit gets a drain: a ``+`` whose two exits reconverge on
    one cell.  Popping a ``0`` sends the IP right into a ``*`` that turns it
    down; popping a ``1`` sends it down around three ``*`` that walk it back
    up and right.  Both arrive at the same cell -- with *different* headings,
    which is fine, because a ``+`` pops on arrival regardless of direction.
    Chaining them steps one row down and one column right per bit::

         +*        the ``+`` pops a stale bit
        *  *       0 goes right then down, 1 goes down then round
        ** +*      both land on the next ``+``

    The drains push nothing, so the ring receives the queue it expects.
    """
    # A ``0`` leaf halts by running off the grid, which no queue content can
    # prevent, so it needs no drain at all -- and paying for one costs real
    # characters: the staircase sits a column right of the branches it
    # replaced, leaving ``_compact`` fewer all-blank columns to drop.
    if value != "1":
        return list(_TREE_0)
    # The leaf is 3x3 placed at (skipped, skipped + 1), so the grid needs
    # ``skipped + 3`` rows and one more column than that.
    grid = [[" "] * (skipped + 4) for _ in range(skipped + 3)]
    for i in range(skipped):
        grid[i][i + 1] = "+"
        grid[i][i + 2] = "*"
        grid[i + 1][i] = "*"
        grid[i + 2][i] = "*"
        grid[i + 2][i + 1] = "*"
    leaf = _TREE_1 if value == "1" else _TREE_0
    for r, line in enumerate(leaf):
        for c, char in enumerate(line):
            if char != " ":
                grid[skipped + r][skipped + 1 + c] = char
    return ["".join(row) for row in grid]


def _tree(values: list[str]) -> list[str]:
    """Build the decision tree for the ``2**n`` table values.

    A subtree whose values all agree folds to a single leaf rather than the
    branches that would all reach it.  The slice's own length says how many
    bits the leaf must drain -- see :func:`_drained_leaf`, which is what
    lets a ``1`` leaf fold at all.
    """
    if len(set(values)) == 1:
        skipped = len(values).bit_length() - 1
        return _drained_leaf(values[0], skipped)
    if len(values) == 2:
        return _connect(
            _TREE_1 if values[0] == "1" else _TREE_0,
            _TREE_1 if values[1] == "1" else _TREE_0,
        )
    half = len(values) // 2
    return _connect(_tree(values[:half]), _tree(values[half:]))


def arrowqueue(truth_table: str) -> str:
    """Build an ArrowQueue template for an ``n``-input Boolean function.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ArrowQueue has no input command, so this is a parameterized generator:
    the returned template's ``{Xi}`` placeholders become the per-bit
    embedding blocks, and the harness instantiates one program per input
    combination (see :func:`_instantiate_arrowqueue`).  Since ArrowQueue has
    no output, the result is read from the termination convention: the
    instantiated program halts iff the table entry for the embedded bits is
    ``0`` and loops forever iff it is ``1``.

    The construction embeds each bit once in the header rows (a ``1`` bit
    pushes down, a ``0`` bit pushes right), queues the right/down/left/up
    loop components, and routes a decision tree by popping the bits at
    ``+`` branches.  Each leaf is a 3x3 block: a ``1`` entry is a
    self-sustaining ring and a ``0`` entry is empty (the pointer runs off
    the grid, which halts).

    A constant subtree folds to a single leaf, which drains the bits the
    skipped branches would have popped -- see :func:`_drained_leaf`.  A
    constant table is 93 characters against 275 at n == 3, and 130 against
    1434 at n == 5.  No program grows: only a ``1`` leaf is drained, since a
    ``0`` leaf halts by running off the grid whatever is queued, and draining
    it anyway cost more than the branches it replaced (AND-2 briefly went
    124 to 128 bytes that way -- it is 109 now).
    """
    n = _validate_truth_table(truth_table)
    if len(truth_table) > 16:
        return _arrowqueue_linear(truth_table, n)
    header = ["{X0}"]
    header.extend(["    "] * 4)
    for i in range(1, n):
        header.append("{X" + str(i) + "}")
        header.extend(["    "] * 3)
    rows = header + _MIDDLE + _tree(list(truth_table))
    return "\n".join(row.rstrip() for row in rows)


def _arrowqueue_linear(truth_table: str, n: int) -> str:
    """Return the marker header and linear marker-count cascade."""
    marker = "".join(f"{{X{i}}}" for i in range(n))
    rows: list[str] = []
    for bit in truth_table:
        stage = [[" "] * 9 for _ in range(3)]
        stage[0][4] = "+"
        if bit == "1":
            for r, line in enumerate(_TREE_1):
                for c, char in enumerate(line):
                    stage[r][6 + c] = char
        rows.extend("".join(row).rstrip() for row in stage)
    return marker + "\n" + "\n".join(rows)


def _instantiate_arrowqueue(template: str, bits: list[int]) -> str:
    """Fill an ArrowQueue template's ``{Xi}`` placeholders with the bits.

    ``bits`` is listed most-significant first and must match the template
    built by :func:`arrowqueue`.  Each ``{Xi}`` placeholder is replaced by
    the embedding block that pushes input ``i`` as a direction: a ``1``
    bit's block pushes down and a ``0`` bit's block pushes right, exactly
    once each (the header is a fixed ``4n + 1`` rows, so the middle and tree
    rows below it stay aligned).
    """
    n = len(bits)
    rows = template.split("\n")
    if n >= 5 and rows[0] == "".join(f"{{X{i}}}" for i in range(n)):
        marker_rows: list[str] = []
        for i, bit in enumerate(bits):
            weight = 1 << (n - 1 - i)
            marker_rows.extend([".~" if bit else ".."] * weight)
        # Enter column 1, append the marker run, turn around, append a right
        # sentinel, then use the established middle block to queue R,D,L,U.
        header = [" *", *marker_rows, "* ~   *"]
        first = list(" " * 7)
        first[0] = first[1] = "*"
        for c, char in enumerate(_MIDDLE[0]):
            first[3 + c] = char
        header.append("".join(first))
        header.extend("   " + row for row in _MIDDLE[1:])
        return "\n".join([*header, *rows[1:]])
    # The header rows are built to a fixed width, but the pointer never
    # travels past the last glyph on a row, so trailing blanks are inert;
    # trim them so the emitted program carries no whitespace it cannot use.
    joined = _header_rows(bits) + rows[4 * n + 1 :]
    return _compact(joined)


def _compact(rows: list[str]) -> str:
    """Drop the wholly blank rows and columns from an instantiated program.

    The blocks are laid out on fixed pitches -- a ``1`` bit's embedding is
    one glyph plus three blank rows, and a tree block pads to 3x3 -- so the
    grid arrives with whole rows and columns that hold no glyph at all.
    They are not spacing the drawing: a blank line carries only straight
    pointer travel (a vertical drop stays in its column, and a run off the
    edge halts either way), so deleting one shortens that travel without
    changing which cell the pointer reaches next or what it pushes and pops
    there.  Deleting rows and columns together keeps every glyph's row and
    column ordering, which is all the routing depends on.

    This runs on the instantiated program rather than in :func:`arrowqueue`
    because the template's blank header rows are reserved slots, not
    padding: :func:`_instantiate_arrowqueue` finds the body by slicing past
    a fixed ``4n + 1`` rows, so compacting them away would misalign it.
    """
    width = max((len(row) for row in rows), default=0)
    padded = [row.ljust(width) for row in rows]
    kept = [row for row in padded if row.strip()]
    if not kept:
        return ""  # pragma: no cover - every table lays a cell
    columns = [x for x in range(width) if any(row[x] != " " for row in kept)]
    return "\n".join("".join(row[x] for x in columns).rstrip() for row in kept)
