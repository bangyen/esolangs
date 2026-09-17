"""Boolean-function generator for ArrowQueue, and the tree it draws."""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    _validate_truth_table,
    fill_runs,
)

# --- ArrowQueue (no-input grid language; parameterized + termination convention) ---
#
# ``*`` turns clockwise, ``~`` pushes the direction, ``+`` pops and points
# (halting on an empty pop).  No I/O, so: parameterized convention (one run
# per input bit, filled by :func:`_instantiate_arrowqueue`) plus the
# termination convention (halt = 0, loop forever = 1; see the limitations
# ledger's halt-vs-hang ring).
#
# Grid layout: the first rows embed each input once (queue holds bits as
# directions, right 0 / down 1); the next rows queue the R/D/L/U loop
# components; the decision tree pops each bit at a ``+``, right for 0 and
# down for 1.  A ``0`` leaf is empty (runs off the grid); a ``1`` leaf is a
# ring that pushes on every edge and pops on every corner.
#
# Every input is one cell, the same cell for every input, every table and
# every arity: ``~`` for a one and ``.`` for a zero.  The pointer crosses
# that cell heading down, so a one pushes a down heading and a zero pushes
# nothing -- ``.`` is a no-op to the interpreter, as every character but
# ``*``, ``~`` and ``+`` is.  What the language does with that one heading
# is the template's business, and the two routes differ there:
#
# - the tree (``n <= 4``) follows each cell with a right push, so a bit is
#   ``D, R`` or ``R`` on the queue; the decision tree pops the front at a
#   ``+`` branch, goes right for ``R`` (a zero) and down for ``D`` (a one),
#   and the down-route pops the trailing ``R`` to turn right again.  A
#   ``0`` leaf is empty, so the pointer runs off the grid and halts; a
#   ``1`` leaf is a ring that pushes on every edge and pops on every corner,
#   sustaining forever on the ``R, D, L, U`` the middle block queues;
#
# - the cascade (``n >= 5``) carries the input's *weight* in the template.
#   Each input sits in a stage that first doubles the down markers already
#   queued -- a loop that pops one marker, re-pushes it and pushes a second
#   -- and then crosses the cell, so after input ``i`` the queue holds
#   ``2 * previous + bit`` markers: Horner's rule, and after the last
#   input exactly the table index.  The stage's tail pushes the right
#   heading that stops the next stage's loop, and the last stage's is the
#   sentinel the vertical cascade below turns right on: one ``+`` per table
#   row pops one marker, the sentinel turns the pointer right at the
#   indexed row, and a zero row runs out of the grid while a one row enters
#   the same sustaining ring as above.
#
# The tree is a full binary tree built from 3x3 blocks: a 0-branch
# (``" + "``) pops the next bit, sending the pointer right for 0 and down
# for 1; a 1-branch (also ``" + "``) pops the one's trailing ``R`` to turn
# the down-route back to the right; and each leaf is a 3x3 output block.
# Connecting two subtrees places a 0-branch at the top-left, the first
# subtree at its right exit, the second at the 1-branch's right exit, and
# the 1-branch at the bottom left (one row below the first subtree),
# filling the rest with spaces.  The pointer enters the whole tree by
# descending column 1 from the loop section, which pops the top-left
# 0-branch's ``+`` directly.

_TREE_1 = ["+~+", "~ ~", "+~+"]  # the ``1`` leaf: a self-sustaining ring


_TREE_0 = ["   ", "   ", "   "]  # the ``0`` leaf: empty, runs off-grid to halt


_TREE_BRANCH_0 = [" + ", "   ", "   "]  # pops a bit; 0 goes right, 1 goes down


_TREE_BRANCH_1 = [" + ", "   ", "   "]  # pops a one's trailing R: down-route goes right


# The loop-component section: entered heading down at column 3 from the
# header (or the last cascade stage), it queues right, down, left, and up
# (in that order, so the queue holds ``[bits..., R, D, L, U]`` at the tree)
# and routes the pointer down column 1 into the tree.
_MIDDLE = ["*~* ", "*  *", "*  *", "~ ~ ", "*~* ", "**  ", "*  *"]


# One cascade stage, entered heading down onto its ``+`` at column 3.  A
# popped down marker walks the loop below: two ``~`` heading down re-push
# it and double it, three ``*`` bring the pointer back onto the ``+`` from
# the left.  The popped right heading -- the previous stage's tail, or the
# first row's -- leaves to the right, turns down through the input cell
# (the ``$`` on the second row, filled with ``~`` or ``.``), and the tail
# hooks left, up, and right past a ``~`` that pushes the right heading the
# next stage's loop stops on, then down onto that stage's ``+``.
_STAGE = ["  *+*", "   ~" + TEMPLATE_CHAR, "   ~", "  **", " *~*", " *  *"]


# One cascade row: the ``+`` at column 1 pops a marker and drops three rows
# to the next, or pops the sentinel and goes right -- into the ring for a
# one, off the grid for a zero.
_CASCADE_1 = [" + +~+", "   ~ ~", "   +~+"]
_CASCADE_0 = [" +", "", ""]


def _header(n: int) -> list[str]:
    """Build the tree route's header: ``n`` input cells, a right push each.

    The first row turns the pointer down onto input 0's cell.  Each cell
    is followed by a hook -- left, up, right past a ``~`` that pushes the
    right heading, down again -- that lands one column left of the cell it
    left, so the cells sit on a diagonal and the last hook exits heading
    down at column 3, where the middle block is entered.
    """
    rows = [" " * (n + 3) + "*"]
    for i in range(n):
        x = n + 3 - i  # input ``i``'s column
        rows.append(" " * (x - 3) + "*~*" + TEMPLATE_CHAR)
        rows.append(" " * (x - 3) + "*  *")
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
    one cell.  Popping a zero's ``R`` sends the IP right into a ``*`` that
    turns it down; popping a one's ``D`` sends it down onto a second ``+``
    that pops the one's trailing ``R`` and sends it right.  Both arrive at
    the same cell -- with *different* headings, which is fine, because a
    ``+`` pops on arrival regardless of direction.  Chaining them steps one
    row down and one column right per bit::

         +*        the ``+`` pops a stale bit
          ++*      ``R`` turns down onto the next ``+``; ``D`` pops its ``R``
           ++*     and walks right onto the same ``+``

    The drains push nothing, so the ring receives the queue it expects.
    """
    # A ``0`` leaf needs no drain (running off the grid halts regardless),
    # and a drain costs ``_compact`` blank columns.
    if value != "1":
        return list(_TREE_0)
    # 3x3 leaf at (skipped, skipped + 1).
    grid = [[" "] * (skipped + 4) for _ in range(skipped + 3)]
    for i in range(skipped):
        grid[i][i + 1] = "+"
        grid[i][i + 2] = "*"
        grid[i + 1][i + 1] = "+"
    for r, line in enumerate(_TREE_1):
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
    the returned template's input runs become the per-bit cells, and the
    harness instantiates one program per input combination (see
    :func:`_instantiate_arrowqueue`).  Since ArrowQueue has no output, the
    result is read from the termination convention: the instantiated
    program halts iff the table entry for the embedded bits is ``0`` and
    loops forever iff it is ``1``.

    Below five inputs the header embeds each bit once, the middle queues
    the right/down/left/up loop components, and a decision tree pops the
    bits at ``+`` branches.  Each leaf is a 3x3 block: a ``1`` entry is a
    self-sustaining ring and a ``0`` entry is empty (the pointer runs off
    the grid, which halts).  A constant subtree folds to a single leaf,
    which drains the bits the skipped branches would have popped -- see
    :func:`_drained_leaf`.

    From five inputs the template is a cascade: one stage per input
    doubles the queued markers and adds the bit, so the marker count is
    the table index, and one ``+`` per table row pops a marker until the
    sentinel turns the pointer right at the indexed row.  The stages are
    ``6n`` rows and the rows ``3 * 2**n``, so the template is linear in
    the table where the tree, whose leaves sit ``3n`` columns deep, is
    not.
    """
    n = _validate_truth_table(truth_table)
    if len(truth_table) > 16:
        rows = ["  ~*", *(_STAGE * n), *_MIDDLE]
        for bit in truth_table:
            rows.extend(
                [" + +~+", "   ~ ~", "   +~+"] if bit == "1" else [" +", "", ""]
            )
        return "\n".join(row.rstrip() for row in rows)
    return "\n".join([*_header(n), *_compact(_MIDDLE + _tree(list(truth_table)))])


def _instantiate_arrowqueue(template: str, bits: list[int]) -> str:
    """Fill an ArrowQueue template's input runs with the bits.

    ``bits`` is listed most-significant first and must match the template
    built by :func:`arrowqueue`.  Every input is one cell, crossed heading
    down: a ``1`` bit's ``~`` pushes a down heading and a ``0`` bit's ``.``
    pushes nothing.  The tree route reads the heading as the bit; the
    cascade counts it at the weight its stage gives it.
    """
    return fill_runs(
        template, TEMPLATE_CHAR, arrowqueue_setters(template, len(bits)), bits
    )


def arrowqueue_setters(template: str, n: int) -> Setters:
    """Return the ``(zero, one)`` cell for every input of ``template``.

    The same cell on both routes and at every input, which is what lets a
    template be filled without knowing which route built it.
    """
    del template
    return ((".", "~"),) * n


def _compact(rows: list[str]) -> list[str]:
    """Drop the wholly blank rows and columns from the template's body.

    The blocks are laid out on fixed pitches -- a tree block pads to 3x3 --
    so the grid arrives with whole rows and columns that hold no glyph at
    all.  They are not spacing the drawing: a blank line carries only
    straight pointer travel (a vertical drop stays in its column, and a run
    off the edge halts either way), so deleting one shortens that travel
    without changing which cell the pointer reaches next or what it pushes
    and pops there.  Deleting rows and columns together keeps every glyph's
    row and column ordering, which is all the routing depends on.

    This runs on the body alone, so the header above it is not consulted.
    That is the same result: the header's rows all hold glyphs, and its
    glyphs sit in columns 1..n+3 while the body's middle block covers 0..3
    on every row and column 4 is a subtree's column 1, which every branch
    marks (``_TREE_BRANCH_0``, ``_TREE_BRANCH_1``) and only a lone ``0``
    leaf leaves blank, where nothing lies to its right for the deletion to
    move.  Columns past 4 hold the header's hooks, which the pointer has
    left for good by the time it enters the body.
    """
    width = max((len(row) for row in rows), default=0)
    padded = [row.ljust(width) for row in rows]
    kept = [row for row in padded if row.strip()]
    if not kept:
        return []  # pragma: no cover - every table lays a cell
    columns = [x for x in range(width) if any(row[x] != " " for row in kept)]
    return ["".join(row[x] for x in columns).rstrip() for row in kept]
