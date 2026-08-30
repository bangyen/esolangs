r"""Boolean-function generators via input-by-substitution.

A normal boolean generator produces one program that *reads* its inputs.
Some languages have no input mechanism but still have enough computation
power (output, constant construction, and a value-testable branch) to
evaluate a boolean function from *embedded* constants.  For those, a
parameterized generator emits a **template** with ``{X0}``.. placeholders
for the input bits; :func:`instantiate` replaces each placeholder with the
language's code that sets that input cell to the bit value.  The harness
instantiates the template once per input and runs it, so the program is a
decision tree over constants rather than a reader of input.

This is a separate class from the input-reading generators: it is useful
exactly for the no-input languages, and it does not make them read input —
the harness performs the injection.  :func:`bio` replaces ``{Xi}`` with an
increment that loads the raw bit into a register; :func:`back` replaces
``{Xi}`` with a ``\\`` or ``/`` mirror so the beam is reflected toward the
correct subtree; :func:`nocomment` replaces ``{Xi}`` with a constant-length
tape setter (``c``/``i``) and routes a decision tree with the ``s`` skip
(a runtime prologue computes each bit's complement via ``s``-as-NOT-gate,
so no ``{Ci}`` is needed); :func:`bitdeque`, :func:`ram0`, and
:func:`minsky_swap` replace ``{Xi}`` with fixed-length setters and route a
``POP``/``GOTO``, ``C``/``goto``, or ``~`` decision tree.

**Every input must be embedded exactly once.**  An input-capable language
reads each of its ``n`` inputs exactly once per run; a no-input language's
parameterized generator should match that, so a template may contain each
``{Xi}`` placeholder at most once.  Re-embedding a bit at multiple decision
nodes would let a no-input program "read" an input more than its
input-capable counterpart does, which muddies the generator API.  Each
generator below therefore stores every input once (a tape load, a register
pack, a deque/stack push, a variable, or a mirror) and reads it back, rather
than re-substituting it.

There is no complement placeholder.  :func:`instantiate` used to fill a
``{Ci}`` beside each ``{Xi}``, for a generator that wanted ``1 - bit``
embedded as a constant, but none does: ``bfpda``'s node structure needs a
truthy marker to stay on the stack after each bit is consumed, and the
marker's value never depends on the bit, so it is a constant written
straight into the template; ``nocomment`` computes each bit's complement
from ``{Xi}`` at runtime with its ``s``-as-NOT-gate.  The placeholder and
the ``set_comp`` argument that filled it are gone.
"""

from collections import deque
from functools import cache

# Re-exported so this module stays the import site for the whole
# parameterized family; each of these owns a file because its
# construction (a search or a grid layout) dwarfs the others.
from esolangs.tools.boolean.a_painter_ant import a_painter_ant
from esolangs.tools.boolean.cod import cod
from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    decision_tree_tokens,
    instantiate,
    permute_truth_table,
)
from esolangs.tools.boolean.minifuck import minifuck
from esolangs.tools.boolean.pct_squared_minus_one import pct_squared_minus_one
from esolangs.tools.boolean.wii2d import wii2d

__all__ = [
    "a_painter_ant",
    "arrowqueue",
    "back",
    "bfpda",
    "bio",
    "bitdeque",
    "cod",
    "eval",
    "instantiate",
    "lamfunc",
    "minifuck",
    "minsky_swap",
    "nocomment",
    "pct_squared_minus_one",
    "ram0",
    "wii2d",
]

# A decision-tree node: ("leaf", leaf_id, value, None, None) or
# ("node", node_id, level, zero_subtree, one_subtree).
type _Node = tuple[str, int, int, _Node | None, _Node | None]


def bio(truth_table: str) -> str:
    """Build a BIO template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BIO has three registers (``x``, ``y``, ``z``) and no absolute jumps —
    its ``{``/``}`` loops are structurally matched — so the setter's length
    is unconstrained.  Each input is embedded once by packing it into ``x``:
    ``{Xi}`` becomes ``0ox`` repeated by the input's binary weight (``2**w``)
    for a one bit, so ``x = sum 2**w_i * bit_i`` is the input's numeric
    index.  A zero writes the same count to ``z`` instead, which nothing
    reads, so the two bits embed at equal width rather than a zero
    embedding as nothing.

    ``y`` is initialized to the table's first entry (``table[0]``), then
    ``2**n - 1`` *nested* loops each decrement ``x`` once (``0ix{ 1ox; ... };``)
    and, on the transition ``table[j-1] -> table[j]``, adjust ``y``: ``0oy``
    for a 0-to-1 rise, ``1oy`` for a 1-to-0 fall, nothing for a flat edge.
    The j-th level fires iff ``x >= j``, so for the packed value ``V`` the
    ops telescope to ``y = table[0] + sum_{j=1}^{V} (table[j] - table[j-1]) =
    table[V]``.  The result is printed with ``1iy``.
    """
    n = _validate_truth_table(truth_table)

    def yop(a: str, b: str) -> str:
        if a == b:
            return ""
        return "0oy;" if a == "0" else "1oy;"

    pack = " ".join("{X" + str(i) + "}" for i in range(n))
    inner = ""
    for j in range(2**n - 1, 0, -1):
        body = "1ox;" + yop(truth_table[j - 1], truth_table[j]) + inner
        inner = "0ix{" + body + "};"
    init = "0oy;" if truth_table[0] == "1" else ""
    return pack + " " + init + inner + "0oy;" * _ASCII_ZERO + "1iy;"


# Eval's two stacks and the ops that move values between them.  ``~`` swaps
# which stack is active, ``*`` reverses the active one, and ``=`` pops the
# active stack onto the other.  The pair is a spindle: moving values across
# reverses them, so composing the three reaches essentially any arrangement.
_EVAL_TREE_STACK, _EVAL_READ_STACK = 0, 1
# Longest op string worth building.  Costs run to roughly 3 characters per
# displaced input, and an arrangement that expensive has already lost to the
# folds it was meant to buy; the cap keeps the search finite.
_EVAL_MAX_OPS = 16
# (tree stack, input stack, which stack is active), each stack listed
# bottom to top by the input index it carries.
type _EvalState = tuple[tuple[int, ...], tuple[int, ...], int]


@cache
def _eval_stack_programs(n: int) -> dict[tuple[int, ...], str]:
    """Shortest ops rearranging the staged bits into each arrangement.

    Returns the input stack (bottom to top, by input index) mapped to the
    ops producing it.  The staging blocks leave the bits on the input stack
    and nothing else, so these ops run between the staging and the tree and
    are free to reverse or shuttle them.

    A breadth-first walk over (tree stack, input stack, active stack) finds
    the shortest.  Only states that end back on the tree stack with nothing
    left staged are usable, since the tree expects to start there.

    **This is a runtime reorder, not a relabelling.**  The ``{Xi}`` blocks
    keep their slots and the harness fills them exactly as before; what
    changes is the emitted program, which now rearranges the stack the nodes
    pop from.  The nodes themselves name no input -- each is ``~=~?`` plus a
    semicolon run fixed by its heap index -- so the arrangement is the only
    thing that decides which input a level tests.
    """
    start: _EvalState = ((), tuple(range(n)), _EVAL_TREE_STACK)
    seen = {start: ""}
    frontier = deque([start])
    reached: dict[tuple[int, ...], str] = {}
    while frontier:
        state = frontier.popleft()
        tree, read, active = state
        ops = seen[state]
        if active == _EVAL_TREE_STACK and not tree and read not in reached:
            reached[read] = ops
        if len(ops) >= _EVAL_MAX_OPS:
            continue

        stacks = {_EVAL_TREE_STACK: tree, _EVAL_READ_STACK: read}
        moves: list[tuple[_EvalState, str]] = [((tree, read, 1 - active), "~")]
        flipped = tuple(reversed(stacks[active]))
        moves.append(
            ((flipped, read, active), "*")
            if active == _EVAL_TREE_STACK
            else ((tree, flipped, active), "*")
        )
        if stacks[active]:
            moved, rest = stacks[active][-1], stacks[active][:-1]
            other = (*stacks[1 - active], moved)
            moves.append(
                ((rest, other, active), "=")
                if active == _EVAL_TREE_STACK
                else ((other, rest, active), "=")
            )

        for next_state, op in moves:
            if next_state not in seen:
                seen[next_state] = ops + op
                frontier.append(next_state)
    return reached


def eval(truth_table: str) -> str:  # noqa: A001 - the language is named "Eval"
    """Build an Eval template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Eval has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a bit push and the harness
    instantiates one program per input combination.  Each is two characters
    wide whichever bit it carries, so the program's shape does not reveal
    its inputs: the bit is staged on the tree stack, where ```` ` ````
    (``1 - ptr``) pushes a one and ``0`` pushes a zero, and ``=`` then moves
    it to the input stack the nodes read.  The tree is stored as a flat, full
    binary tree in heap (BFS) order on the tree stack; a node at index
    ``i`` tests the next input and the heap layout pins its two children at
    fixed offsets.

    A node is ``~=~?`` followed by ``i+1`` semicolons and a ``!``: ``~``
    switches to the input stack, ``=`` moves the top input onto the tree
    stack, ``~`` switches back, and ``?`` pops it -- skipping the next
    command when it is zero.  The ``;``s discard ``i+1`` elements when the
    bit is one (the skip makes it ``i`` when zero), so ``!`` pops the
    0-child (heap index ``2i+1``) for a zero bit and the 1-child (``2i+2``)
    for a one.  A leaf is ``0+.`` (prints 1) or ``0.`` (prints 0).  The
    template pushes the tree in BFS order, reverses the stack so the root
    is on top, and ``!`` evaluates it; each path keeps popping bits until a
    leaf prints.  No node or leaf contains a quote or backtick, so the
    strings need no escaping and the tree grows to any ``n``.

    A node whose rows all agree becomes the leaf it would have reached, and
    its descendants become empty strings.  The fold has to work that way
    round: the heap is *positional*, so the ``;`` run is a function of the
    node's own index and every child sits at a pinned ``2i+1``/``2i+2``, and
    deleting a subtree the way a token-stream generator does would shift
    every later index and misroute the whole tree.  Emptying the slots
    instead leaves the arithmetic untouched, and an emptied slot is never
    popped because the only node that routed into it has become a leaf.  A
    constant table goes from 127 to 47 characters at ``n == 3``.
    """
    n = _validate_truth_table(truth_table)
    # The staging leaves the input stack holding only the bits and nothing
    # else, so the tree can be preceded by ops that rearrange them.  Every
    # reachable arrangement is a candidate, including the one staging
    # already produces, which costs no ops.
    #
    # The tree pops the input stack top-first, so an arrangement listed
    # bottom-to-top tests its *last* entry at the root: the split order is
    # the arrangement reversed.  Staging pushes X0 first, so the free
    # arrangement is ``(0, ..., n-1)`` and its split order is the reversal
    # -- which is why the no-ops candidate is not the identity permutation.
    best = ""
    for arrangement, ops in sorted(
        _eval_stack_programs(n).items(), key=lambda item: len(item[1])
    ):
        perm = tuple(reversed(arrangement))
        candidate = _eval_ordered(permute_truth_table(truth_table, perm), ops)
        # Sorted by op cost with the free arrangement first, and the
        # comparison is strict, so a table no reorder helps emits exactly
        # what it emitted before.
        if not best or len(candidate) < len(best):
            best = candidate
    return best


def _eval_ordered(truth_table: str, ops: str) -> str:
    """Emit one input order's Eval template; see :func:`eval`.

    ``truth_table`` is already permuted, so the heap walk below is unchanged
    from the single-order construction.  What the emitted program does
    differently is run ``ops`` between the staging blocks and the tree,
    rearranging the input stack so the nodes pop the bits in this order.
    """
    n = _validate_truth_table(truth_table)

    def combo(leaf: int) -> tuple[int, ...]:
        """Input bits (most significant first) reaching the heap ``leaf``."""
        path: list[int] = []
        while leaf > 0:
            path.append(0 if leaf % 2 else 1)  # odd = left child = 0 branch
            leaf = (leaf - 1) // 2
        return tuple(reversed(path))

    def rows_under(i: int) -> list[int]:
        """Table rows reachable from heap node ``i``."""
        if i >= 2**n - 1:
            return [sum(b << (n - 1 - k) for k, b in enumerate(combo(i)))]
        return rows_under(2 * i + 1) + rows_under(2 * i + 2)

    # A node whose rows all agree is replaced, *in its own slot*, by the leaf
    # it would have reached.  The heap is positional -- every node's children
    # are pinned at 2i+1/2i+2 and its own ``;`` run is a function of ``i`` --
    # so a folded subtree cannot be deleted the way a token-stream tree's
    # can, or every later index would shift.  Leaving the slots in place and
    # emptying them keeps all of that arithmetic untouched: an empty string
    # is never popped, because the only node that routed into it is gone.
    dead: set[int] = set()
    tree: list[str] = []
    for i in range(2 ** (n + 1) - 1):
        if i in dead:
            tree.append("")
            continue
        rows = rows_under(i)
        values = {truth_table[row] for row in rows}
        if i < 2**n - 1 and len(values) == 1:
            tree.append("0+." if values.pop() == "1" else "0.")
            below = [2 * i + 1, 2 * i + 2]
            while below:  # the whole subtree, not just the two children
                child = below.pop()
                dead.add(child)
                if child < 2**n - 1:
                    below += [2 * child + 1, 2 * child + 2]
        elif i < 2**n - 1:  # internal node: test the next input
            tree.append("~=~?" + ";" * (i + 1) + "!")
        else:  # leaf: print the table entry for this path
            tree.append("0+." if truth_table[rows[0]] == "1" else "0.")

    # Staged forward, like every other parameterized generator.  The order
    # is a free choice rather than a constraint: it decides only *which*
    # arrangement costs no ops, and the reachable set and every other
    # arrangement's cost are identical either way, because ``*`` is an
    # involution -- staging one way and reversing is the other way exactly.
    bits = "".join("{X" + str(i) + "}" for i in range(n))
    return bits + ops + "".join(f'"{t}"' for t in tree) + "*!"


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
    tree.  The load is therefore written bottom-to-top, and the tree is free
    to begin one column in.

    The answer is therefore the *value* of cell ``n``, which the halt dump
    prints, rather than the head's position, which it does not.  An earlier
    layout kept a 0-cell and a 1-cell and parked the head on whichever
    matched; that made the result unreadable from the program's own output,
    so Back could have no committed example and its generator tests had to
    reimplement the language to find the head.  One answer cell costs
    nothing -- a leaf spends one ``-`` instead of one extra pointer move --
    and makes the dump self-describing.
    """
    return best_input_order(truth_table, _back_ordered)


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
    walk at all, because the pointer only ever steps one cell forward, and
    it delivered the full 12.0% screen against the 9.15% here.  That build
    is not kept: it puts the template's placeholders out of name order, and
    every other generator in this module emits ``{X0}``..``{Xn-1}`` in
    sequence.  Both forms are correct -- ``instantiate`` substitutes by
    *name*, so a placeholder is filled wherever it sits -- so this is a
    consistency choice rather than a correctness one, and it costs 2.85
    points.

    The walk is cheap in absolute terms (two characters a move: the
    character, plus the newline its own load row carries) and shows up as
    2.85 points only because Back's programs are small -- 82 characters on
    average at n=3, against LaserFuck's 326.

    Keeping the ``-``/``{Xi}`` pairs intact is what preserves the
    equal-width embedding: the primer and the placeholder are one unit and
    are never separated, so both bits still cost the same two rows and the
    template's height cannot leak an input.
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
    # Filling in cell order instead (cell ``c`` taking ``{X perm[c]}``) would
    # emit no walk at all and is what this generator did briefly: it costs
    # nothing and delivers the full 12.0% screen against the 9.15% here.  It
    # is not kept, because it puts the template's placeholders out of name
    # order, and every other generator in this module emits ``{X0}``..
    # ``{Xn-1}`` in sequence.  The saving is real but the exception is not
    # worth it; see the docstring for the trade.
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
    # a second time, now heading up, and turns it right into the tree.  So the
    # load is written bottom-to-top, and an earlier layout's two '\' -- one to
    # drop the beam off the load's end, one to turn it back right -- are both
    # gone along with the row and the indent they cost.
    #
    # Riding off the top edge makes the grid's toroidal wrap load-bearing:
    # ``_Machine.step`` advances with ``% len(code)``, so up from row 0 lands
    # on the last row.  The wiki text the interpreter quotes does not mention
    # the edges at all, and no interpreter test covers a wrap, so this is the
    # one place the generator leans on behaviour with no witness outside this
    # repo's own interpreter.
    grid: dict[tuple[int, int], str] = {}
    next_row = [1]

    def leaf(level: int, value: str, row: int, col: int) -> None:
        # walk to the single answer cell, write a 1 there when the leaf's
        # value is 1 (it starts 0), and halt
        delta = n - level
        move = (">" if delta >= 0 else "<") * abs(delta)
        code = move + ("-" if value == "1" else "") + "*"
        for k, ch in enumerate(code):
            grid[(row, col + k)] = ch

    def emit(level: int, lo: int, hi: int, row: int, col: int) -> None:
        vals = {truth_table[r] for r in range(lo, hi)}
        if level == n or len(vals) == 1:
            leaf(level, vals.pop() if level < n else truth_table[lo], row, col)
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
    # n = 3 the tree is the taller of the two, so the load's rows start
    # sharing with tree rows -- which is safe for the same reason the whole
    # template is: a '{Xi}' is the only thing on its row that instantiation
    # resizes, it always shrinks by exactly three (every embedding is one
    # character, for either bit value), and it sits left of the tree, so the
    # tree glyphs on that row slide back to the columns they were drawn for.
    # An embedding whose width depended on the bit would break that silently.
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
    return "\n".join("".join(row).rstrip() for row in rows)


# The largest value a NoComment cell can hold, hence the largest distance a
# single ``s``/``b`` jump can cover: the skip amount is peeked off the stack,
# and everything on that stack came from a byte-sized tape cell.
_NOCOMMENT_SKIP_MAX = 255

# Past this arity the *index* no longer fits one byte, so the single-skip
# decode below stops working and :func:`_nocomment_wide` takes over.  It is
# the largest ``n`` with ``2**n - 1 <= _NOCOMMENT_SKIP_MAX``.
_NOCOMMENT_NARROW_MAX = (_NOCOMMENT_SKIP_MAX + 1).bit_length() - 1


def _nocomment_summand_plan(n: int, room: int) -> list[list[tuple[int, int]]]:
    """Split the index's bit weights into cells that cannot overflow a byte.

    The index is ``sum(2**(n-1-i) for i where bit i is one)``, which exceeds
    a byte past ``n == 8``.  Splitting it into *summands* rather than digits
    keeps every part byte-sized and keeps each part a plain sum of per-bit
    contributions, so each contribution stays a guarded increment.

    Returns one list of ``(bit, amount)`` pairs per summand cell.  A cell's
    amounts total at most ``_NOCOMMENT_SKIP_MAX``, so no input can push it
    past a byte, and each single contribution is at most ``room`` so the
    guarded block that adds it stays within one skip.
    """
    parts: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    total = 0
    for i in range(n):
        remaining = 2 ** (n - 1 - i)
        while remaining:
            if total == _NOCOMMENT_SKIP_MAX:
                parts.append(current)
                current, total = [], 0
            take = min(remaining, _NOCOMMENT_SKIP_MAX - total, room)
            current.append((i, take))
            total += take
            remaining -= take
    if current:
        parts.append(current)
    return parts


def _nocomment_wide(truth_table: str, n: int) -> str:
    """Build a NoComment template for a table too wide for one byte-sized skip.

    The narrow generator lands the pointer on ``table[index]`` with a single
    ``s`` whose skip amount *is* the index, which caps it at ``n == 8``.
    Nothing about the language caps it there, though, because **skips
    compose**.  Two compositions do the work:

    *Chained guards.*  ``s`` peeks the stack rather than popping it and does
    not move the pointer, so after a skip fires the guard cell is still under
    the pointer and still nonzero.  A guarded region of any length is then a
    run of chunks, each at most ``_NOCOMMENT_SKIP_MAX`` commands and each
    preceded by glue that rebuilds the chunk's length and re-tests the same
    guard.  Every chunk ends with the pointer back on the guard, so the glue
    -- which runs on both paths -- is emitted from one known position.

    *Additive staircases.*  Entering a staircase of ``L`` copies of ``l`` by
    skipping ``c`` runs ``L - c`` of them, so pre-walking ``L`` right and
    then skipping ``c`` is a net move of ``+c``.  Displacements add across
    consecutive staircases, so a displacement far past 255 is reached by
    ``q`` stages whose skip amounts sum to it, each stage's amount held in
    its own byte-sized summand cell.

    Between stages the stack top must advance, and ``f`` is the only way to
    pop -- it writes the popped value into the cell under the pointer.  That
    clobber is harmless because it always lands mid-corridor: a **constant**
    trailing summand of ``1`` is appended so the final landing is strictly
    right of every clobbered cell, which is what makes the all-zero input
    (every input-driven summand zero) come out right.

    What binds instead is the tape.  The layout needs the ``2**n`` output
    cells plus an apron of nonzero cells for the stages' guards to test, and
    :mod:`~esolangs.interpreters.tape_based.nocomment` gives a static tape,
    so the generator refuses when the top cell it needs does not fit.  The
    wiki does not specify a tape size, so that bound is the interpreter's
    configuration rather than a property of the language.
    """
    from esolangs.interpreters.tape_based.nocomment import _TAPE

    cap = _NOCOMMENT_SKIP_MAX
    k = 2**n
    comp_base = n  # comp_i = 1 - bit_i
    sbase = 2 * n  # the summand cells

    # The furthest summand cell sets how long a guarded contribution's
    # move-add-return block is, which sets how much of one contribution fits
    # in a single skip.  Planning with the worst-case distance keeps every
    # emitted skip within a byte without a second pass.
    plan = _nocomment_summand_plan(n, 1)
    span = len(plan) + 1
    room = cap - 2 * (sbase + span - 1 - comp_base)
    if room > 0:
        plan = _nocomment_summand_plan(n, room)
    q = len(plan) + 1  # the input-driven summands plus the constant one
    scratch = sbase + q
    base = scratch + 1
    apron = base + k
    # Each stage pre-walks a full staircase right of its landing cell before
    # testing, so the guard apron must cover one staircase past the table,
    # and the walk itself reaches one staircase past that.
    top = apron + 2 * cap + 1
    if top >= _TAPE:
        raise ValueError(
            f"the NoComment boolean generator needs cell {top} for n == {n}, "
            f"past the interpreter's {_TAPE}-cell tape"
        )

    out: list[str] = []
    ptr = [0]

    def move(dst: int) -> None:
        while ptr[0] < dst:
            out.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            out.append("l")
            ptr[0] -= 1

    def guarded(guard: int, chunks: list[list[str]]) -> None:
        """Emit a region that runs iff ``guard`` is zero, chunked to fit skips.

        Each chunk must start and end with the pointer on ``guard``.  The
        glue rebuilds the chunk's length in ``scratch``, pushes it, returns
        to the guard, and skips -- so the skip path never leaves the guard
        and the fall-through path is returned there by the chunk itself.
        """
        for chunk in chunks:
            move(scratch)
            out.append("c")
            out.extend(["i"] * len(chunk))
            out.append("n")
            move(guard)
            out.append("s")
            out.extend(chunk)
            ptr[0] = guard

    for i in range(n):
        out.append("{X" + str(i) + "}")
        out.append("r")
    ptr[0] = n

    # comp_i = 1 - bit_i: the block runs exactly when bit i is zero.
    for i in range(n):
        dist = comp_base + i - i
        guarded(i, [["r"] * dist + ["i"] + ["l"] * dist])

    for j in range(q):
        move(sbase + j)
        out.append("c")

    # The output table, then an apron of nonzero cells so every stage's
    # pre-walk lands on a truthy guard.  Both are constants, so they go
    # through one sorted diff chain: sorting by value makes each step a
    # single push/pop plus the difference from the previous value.
    cells: list[tuple[int, int]] = [
        (base + j, _ASCII_ZERO + int(truth_table[j])) for j in range(k)
    ]
    cells += [(apron + t, _ASCII_ZERO) for t in range(2 * cap + 1)]
    cells.sort(key=lambda cv: cv[1])
    first_addr, first_value = cells[0]
    move(first_addr)
    out.extend(["i"] * first_value)
    prev_value = first_value
    for addr, value in cells[1:]:
        out.append("n")
        move(addr)
        out.append("f")
        diff = value - prev_value
        out.extend(["i"] * diff if diff > 0 else ["d"] * -diff)
        prev_value = value

    # Bit i adds its share to each summand cell it feeds.  The guard is the
    # complement, so the block runs exactly when the bit is one.
    for j, part in enumerate(plan):
        cell = sbase + j
        for i, amount in part:
            guard = comp_base + i
            dist = cell - guard
            chunks = []
            remaining = amount
            while remaining:
                take = min(remaining, cap - 2 * dist)
                chunks.append(["r"] * dist + ["i"] * take + ["l"] * dist)
                remaining -= take
            guarded(guard, chunks)

    move(sbase + q - 1)
    out.append("c")
    out.append("i")  # the constant trailing summand

    # Push the summands so the first stage sees the first one on top.
    for j in reversed(range(q)):
        move(sbase + j)
        out.append("n")

    # The trailing summand contributes the final ``+1``, so the walk starts
    # one cell left of the table and ends on ``base + index``.
    move(base - 1)
    for j in range(q):
        if j:
            # Advance the stack top.  ``f`` writes the popped summand into
            # the cell under the pointer, which is always a corridor cell at
            # least one staircase left of any cell a later stage tests.
            out.append("f")
        out.extend(["r"] * cap)
        out.append("s")
        out.extend(["l"] * cap)
    out.append("o")
    return "".join(out)


def nocomment(truth_table: str) -> str:
    """Build a NoComment template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    NoComment has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a constant-length setter for each
    input bit, and the harness instantiates one program per input
    combination.  Unlike an earlier version of this generator, the
    complement is *not* embedded: NoComment's ``s`` (skip the next block iff
    the tested cell is nonzero) doubles as a NOT gate, because the skipped
    block only runs when the cell is zero.  A short runtime prologue pushes
    a fixed skip length, tests each raw bit cell, and increments a fresh
    complement cell in the skipped block -- so ``comp_i = 1 - bit_i`` is
    computed once per input from the embedded bit, with no ``{Ci}``
    placeholder and no second embed.

    Rather than routing a decision tree, the program **computes the input's
    numeric index** and uses it as a byte-sized ``s`` skip into a staircase of
    ``l`` moves that land the pointer on a pre-loaded output cell holding
    ``48 + truth_table[index]``.  Each bit ``i`` contributes its weight
    (``2**w``) to the index cell only when the bit is one -- the guard tests
    the complement cell so the contribution is skipped when the bit is zero.
    The output is then a single ``o``.

    This is a straight-line program: no leaf chains, no interleaved stations,
    no placement.  A single ``s`` skip is byte-sized, so this narrow form
    needs the whole index to fit a byte and works through ``n == 8``.  That
    is a property of the *one-skip* decode, not of the language: past eight
    inputs :func:`_nocomment_wide` composes several byte-sized skips instead,
    and the binding constraint becomes the interpreter's tape size.
    """
    n = _validate_truth_table(truth_table)
    if n > _NOCOMMENT_NARROW_MAX:
        return _nocomment_wide(truth_table, n)

    k = 2**n
    index = 2 * n
    skip_base = index + 1  # one skip cell per input bit
    tbase = skip_base + n  # the output cells
    sentinel = tbase + k  # non-zero cell the final ``s`` gates on
    scratch = sentinel + 1  # reused per bit to push each NOT gate's skip length

    # Emit the index computation and the output staircase.  Each bit's
    # guarded increment ends with the pointer back on its complement cell,
    # so the emitted moves stay consistent.
    commands: list[str] = []
    ptr = [index]

    def move(dst: int) -> None:
        while ptr[0] < dst:
            commands.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            commands.append("l")
            ptr[0] -= 1

    skip_vals: dict[int, int] = {}
    for i in range(n):
        w = n - 1 - i
        comp = n + i
        d = skip_base + i
        move(d)
        commands.append("n")
        move(comp)
        commands.append("s")
        block = len(commands)
        move(index)
        commands.extend(["i"] * (2**w))
        move(comp)
        skip_vals[d] = len(commands) - block
    move(index)
    commands.append("n")  # push the index
    ptr[0] = index
    move(sentinel)
    commands.append("s")  # skip by the index into the staircase
    commands.extend(["l"] * k)
    commands.append("o")

    # Setup: bits, complements, index, skip cells, output cells, sentinel,
    # scratch.  The complement cells (n..2n-1) start at zero and are filled
    # by the NOT-gate prologue below, not by a {Ci} placeholder.
    setup: list[str] = []
    setup_ptr = [0]

    def setup_move(dst: int) -> None:
        while setup_ptr[0] < dst:
            setup.append("r")
            setup_ptr[0] += 1
        while setup_ptr[0] > dst:
            setup.append("l")
            setup_ptr[0] -= 1

    for i in range(n):
        setup.append("{X" + str(i) + "}")
        setup.append("r")
    setup_ptr[0] = n

    # NOT-gate prologue: for each bit i, comp_i = 1 - bit_i.  ``s`` at the
    # bit cell skips a fixed-length block (move to comp_i, set it, move back)
    # exactly when the bit is nonzero, so the block runs -- and increments
    # the complement cell -- only when the bit is zero.  Both the skip and
    # fall-through paths leave the pointer back on the bit cell, so the
    # next bit's prologue starts from a known position.
    for i in range(n):
        comp = n + i
        # comp is always to the right of bit i (comp - i == n), so the gate
        # is a straight-line move-set-return with no branching to track.
        dist = comp - i
        gate = ["r"] * dist + ["i"] + ["l"] * dist
        gate_len = len(gate)

        setup_move(scratch)
        setup.append("c")
        setup.extend(["i"] * gate_len)
        setup.append("n")  # push gate_len
        setup_move(i)
        setup.append("s")
        setup.extend(gate)

    setup_move(index)
    setup.append("c")  # index starts at zero
    cells: list[tuple[int, int]] = list(skip_vals.items())
    cells.append((sentinel, _ASCII_ZERO))
    for j in range(k):
        cells.append((tbase + j, _ASCII_ZERO + int(truth_table[j])))
    cells.sort(key=lambda cv: cv[1])
    if cells:
        first_addr, first_value = cells[0]
        setup_move(first_addr)
        setup.extend(["i"] * first_value)
        prev_value = first_value
        for addr, value in cells[1:]:
            setup.append("n")
            setup_move(addr)
            setup.append("f")
            diff = value - prev_value
            setup.extend(["i"] * diff if diff > 0 else ["d"] * -diff)
            prev_value = value
    setup_move(index)

    return "".join(setup + commands)


def bfpda(truth_table: str) -> str:
    """Build a BF-PDA template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BF-PDA has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a push of the bit, four
    characters wide whichever bit it is, so the program's shape does not
    reveal its inputs.  The harness instantiates one program per input
    combination.  Each input is embedded once: the load phase pushes every
    ``<@{Xi}`` pair (a constant 1 marker, then the bit) up front, so the
    stack holds all ``n`` bits and markers with ``b0`` on top.

    Every character outside ``@.<>[]`` is a comment, so the commands are
    emitted unseparated; the fragments below are spaced only to read.

    A node tests its bit and *consumes* it for the next level using a
    ``<``-break loop ``[ > one < ] > [ > zero < ] >``: ``[`` enters when the
    bit is one, ``>`` pops it, the one-branch pops the marker (to expose the
    next bit), and ``<`` pushes a fresh zero to break the loop -- which
    works because the guard was already popped, unlike ``[ sub @ ]`` where
    ``@`` needs the guard still on top.  The zero-branch is selected by the
    second loop testing the marker: when the bit is zero, ``[`` never
    entered, so the outer ``>`` pops the *bit* instead (it was never
    consumed), exposing the marker as the new top.  The marker's role is
    only to be truthy there -- its value never depends on the input, so a
    constant 1 (not the input's complement) is correct, and it is embedded
    directly in the template rather than through the bit-value substitution.
    A leaf pops the remaining pre-loaded bits (``2*(n-level)`` of them) and
    prints the constant answer.
    """
    n = _validate_truth_table(truth_table)

    # Load: push a constant-1 marker then the bit, in name order, so the top
    # of the stack is the *last* input and the tree tests it first.
    #
    # The load used to run reversed so the top was ``b0`` and level ``i``
    # could test input ``i``.  That is the only thing the reversal bought,
    # and testing the inputs bottom-up costs nothing: the stack is strictly
    # LIFO either way, every level still consumes exactly one bit and one
    # marker, and the tree is the same shape reflected.  Pushing in name
    # order keeps the emitted template in ``{X0}``..``{Xn-1}`` sequence.
    head = "".join("<@{X" + str(i) + "}" for i in range(n))

    def leaf(level: int, value: str) -> str:
        # consume the remaining pre-loaded bits, then print the answer
        return ">" * (2 * (n - level)) + ("<@" if value == "1" else "<") + ".>"

    # Not routed through :func:`decision_tree_tokens`: this tree is a plain
    # string with no index to thread, so the walker's token lists would have
    # to be one-element lists unwrapped at every use, which reads worse than
    # the four lines it saves.
    def node(i: int, rows: list[int]) -> str:
        results = {truth_table[r] for r in rows}
        if i == n or len(results) == 1:
            return leaf(i, results.pop() if i < n else truth_table[rows[0]])
        # The load pushes in name order, so the stack hands back the *last*
        # input first: level ``i`` tests input ``n - 1 - i``, whose row bit
        # is at position ``i``.
        zero = [r for r in rows if ((r >> i) & 1) == 0]
        one = [r for r in rows if ((r >> i) & 1) == 1]
        sub0 = node(i + 1, zero)
        sub1 = node(i + 1, one)
        # one-branch pops ~bi first (expose next bit); zero-branch has it popped
        # by the node's own loop
        return "[>" + ">" + sub1 + "<]>[>" + sub0 + "<]>"

    return head + node(0, list(range(2**n)))


def lamfunc(truth_table: str) -> str:
    """Build a Lamfunc template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Lamfunc has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become the binary literal for each input
    bit, and the harness instantiates one program per input combination.

    Each input is stored once in a variable (``vs v{i} {Xi}``), so the inputs
    are embedded exactly ``n`` times; the decision tree then reads each bit
    back with ``vg v{i}`` instead of re-embedding it at every node.  The tree
    is a chain of ``i`` builtins — ``i x y z`` returns ``y`` when ``x`` is
    nonzero else ``z`` — with ``p 0``/``p 1`` at the leaves printing the
    table's result as binary.  A subtree whose table slice is a constant
    collapses to a single leaf, so constant rows emit no branching.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.boolean.helpers.best_input_order`),
    since whether a subtree collapses depends on which rows it covers, and
    that is what the split order decides.  Reading a bit back is by *name*,
    so the reorder costs nothing here: the ``vs v{i} {Xi}`` head still
    stores input ``i`` in ``v{i}``, and only the variable a node names
    changes.
    """
    return best_input_order(truth_table, _lamfunc_ordered)


def _lamfunc_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Lamfunc template; see :func:`lamfunc`.

    ``truth_table`` is already permuted, so the ``lo``/``hi`` row span is
    in the permuted frame; ``perm`` is spent only on the variable a node
    reads back, ``v{perm[level]}``.
    """
    n = _validate_truth_table(truth_table)

    def node(level: int, lo: int, hi: int) -> str:
        results = {truth_table[k] for k in range(lo, hi)}
        if level == n or len(results) == 1:
            return f"p {results.pop()}"
        mid = (lo + hi) // 2
        # i x y z returns y when x is nonzero else z: y is the one-case
        return (
            f"i vg v{perm[level]} {node(level + 1, mid, hi)} {node(level + 1, lo, mid)}"
        )

    head = " ".join(f"vs v{i} {{X{i}}}" for i in range(n))
    return head + " " + node(0, 0, 2**n)


def bitdeque(truth_table: str) -> str:
    """Build a Bitdeque template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Bitdeque has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a *fixed-length* two-command
    setter per bit, and the harness instantiates one program per input
    combination.  The earlier wall said the absolute ``GOTO N`` targets shift
    because the setter had variable length (``INVERT`` vs nothing); the fixed
    setter removes that: each bit is pushed as exactly ``INVERT PUSH`` when
    it differs from the register and ``PUSH INVERT`` when it matches, and
    the register flips after every block, so the load is always ``2n``
    commands and no absolute index moves between instantiations.

    Bits are pushed in reverse order so ``POP`` (LIFO) yields the most
    significant bit first, matching the contiguous MSB-first decision-tree
    splits.  A node pops one bit and ``GOTO``s to the one-subtree when it is
    one, with the zero-subtree falling through in place.  A leaf drains the
    deque with ``n+1`` ``POP``s (so the register is exactly zero even for a
    collapsed tree), pushes the answer, forces the register back to one with
    a trailing ``INVERT``, and ``GOTO``s past the program end to halt -- so
    every leaf always routes and the deque printed at halt holds exactly the
    answer.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.boolean.helpers.best_input_order`).
    Bitdeque is a *deque*, not a stack: ``INJECT``/``EJECT`` work the head
    where ``PUSH``/``POP`` work the tail, so a node can bring any bit to an
    end with ``EJECT PUSH`` (head to tail) or ``POP INJECT`` (tail to head)
    and is not restricted to the order the load pushed.  Rotation costs two
    commands per position, so an order pays for its folds; the search
    measures rather than models, and an order whose rotations outweigh its
    savings simply loses to the identity.

    The rotations happen *inside the tree*, never in the load block: the
    ``{Xi}`` setter's ``INVERT PUSH``/``PUSH INVERT`` choice depends on the
    register parity at its position, so moving the head would desync every
    fill site.  The emitted load is byte-identical whatever the order.
    """
    return best_input_order(truth_table, _bitdeque_ordered)


def _bitdeque_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Bitdeque template; see :func:`bitdeque`.

    ``truth_table`` is already permuted, so the rows are in the permuted
    frame.  ``perm`` is spent on the rotations a node runs before it
    consumes its bit -- and those are a function of the *level* alone, not
    of the node: both branches of a level have rotated and consumed exactly
    the same bits on the way down, so the deque layout at a level is the
    same on every path through it.  That is what keeps a node's width
    well-defined for the walker's index arithmetic.

    Under the identity order every bit is already at the tail when it is
    wanted, so no rotation is emitted and the output is byte-identical to
    what the unordered generator produced.
    """
    n = _validate_truth_table(truth_table)

    def leaf(answer: str) -> list[str]:
        out = ["POP"] * (n + 1)
        if answer == "1":
            out.append("INVERT")
        out.append("PUSH")
        if answer == "0":
            out.append("INVERT")
        out.append("GOTO@END")
        return out

    # Simulate the deque to find each level's rotation.  The load pushes the
    # inputs in name order, so the tail -- what ``POP`` returns -- is input
    # ``n - 1`` and the head is input 0.
    #
    # Pushing in name order rather than reversed is free.  The reversed load
    # was there to make the first ``POP`` the *most significant* bit, which
    # only fixes which input a root-level test reaches first -- and the
    # rotation search already brings any bit to either end, so both loads
    # reach the same set of orders at the same cost.  Measured over every
    # order at n = 2, 3 and 4, the rotation-length multisets are identical.
    # Name order is the better default because it keeps the emitted template
    # in ``{X0}``..``{Xn-1}`` sequence.
    deque = list(range(n))
    rotations: list[list[str]] = []
    for level in range(n):
        want = perm[level]
        index = deque.index(want)
        from_tail = len(deque) - 1 - index
        if from_tail <= index:
            # Nearer the tail: rotate the tail round to the head, then POP.
            rotations.append(["POP", "INJECT"] * from_tail + ["POP"])
            for _ in range(from_tail):
                deque.insert(0, deque.pop())
            deque.pop()
        else:
            # Nearer the head: rotate the head round to the tail, then EJECT.
            rotations.append(["EJECT", "PUSH"] * index + ["EJECT"])
            for _ in range(index):
                deque.append(deque.pop(0))
            deque.pop(0)

    def width(level: int) -> int:
        # the rotation, its consuming pop, and the node's own ``GOTO``
        return len(rotations[level]) + 1

    # the load block, in name order; each placeholder expands to two commands
    head = ["{X" + str(i) + "}" for i in range(n)]

    # A node spends its rotation, its pop and its ``GOTO`` before either
    # subtree, so the walker's ``at`` lands on this node and ``at +
    # width(level)`` on the zero subtree.  The load block occupies ``2n``
    # commands ahead of the tree, which is where the indices start, so the
    # ``GOTO`` operands are right after substitution.
    tree = decision_tree_tokens(
        truth_table,
        lambda _level, row: leaf(truth_table[row]),
        lambda level, zero, one, at: [
            *rotations[level],
            f"GOTO {at + width(level) + len(zero)}",
            *zero,
            *one,
        ],
        parent_width=width,
        start=2 * n,
        collapse=True,
    )
    end = 2 * n + len(tree)
    return " ".join(head + ["GOTO " + str(end) if t == "GOTO@END" else t for t in tree])


def _ram0_width(address: int) -> int:
    """Commands a RAM0 tree node spends before its subtrees.

    ``Z``, an ``A`` per unit of the cell address, ``L``, ``C``, and the
    ``goto`` that reaches the one-subtree -- so the width varies from node
    to node, which is why the walker takes a callable rather than a
    constant.  The address is the *input* the node tests, which is its
    level only under the identity order; :func:`_ram0_ordered` maps one to
    the other.
    """
    return address + 4


def ram0(truth_table: str) -> str:
    """Build a RAM0 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    RAM0 has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a fixed-length two-command
    setter — ``Z Z`` for a zero, ``Z A`` for a one — independent of the
    incoming register (``Z`` resets absolutely).  The earlier wall's
    variable-length setter (``Z`` vs ``Z A``) was what shifted the absolute
    ``goto`` operands; the padded setter removes that.

    A load phase stores each bit once in its own RAM cell (address ``i``),
    so the inputs are embedded exactly ``n`` times; the decision tree then
    *loads* each bit with RAM0's indirect ``L`` (``z := ram[z]``) rather than
    re-embedding it, so the tree nodes contain no substitution.  Each node
    sets ``z`` to its address, loads the bit, and ``C`` skips the following
    ``goto`` when ``z`` is zero (the zero-subtree falls through in place)
    while the ``goto`` jumps to the one-subtree otherwise.  A leaf sets
    ``z`` to the answer and uses RAM0's *unconditional* ``goto`` to run off
    the program end, so the final ``z`` read from the state dump is the
    answer.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.boolean.helpers.best_input_order`).
    Folding a subtree needs the rows it covers to agree, and which rows a
    subtree covers is what the split order decides; RAM0 also spells an
    input as a run of ``A`` as long as its *address*, so a cheap order here
    additionally wants the low addresses at the deep, oft-repeated levels.
    Both effects come out of measuring the emitted candidates rather than
    modelling either.  The load phase still stores bit ``i`` in cell ``i``
    in input order, so the ``{Xi}`` placeholders and their positions are
    untouched -- only which cell a node loads moves.
    """
    return best_input_order(truth_table, _ram0_ordered)


def _ram0_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's RAM0 template; see :func:`ram0`.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame.  ``perm`` is spent on the address a node names: the
    ``A`` run is ``perm[level]`` long, which is also what makes the node's
    width -- and therefore every absolute ``goto`` operand below it --
    depend on the order.
    """
    n = _validate_truth_table(truth_table)

    def width(level: int) -> int:
        return _ram0_width(perm[level])

    tokens: list[str] = []
    pos = 0  # instantiated command index of the next command

    # load phase: ram[i] = bit i, embedded exactly once each
    for i in range(n):
        tokens.append("Z")
        tokens.extend("A" for _ in range(i))
        tokens.append("N")
        pos += 1 + i + 1
        tokens.append("{X" + str(i) + "}")  # expands to "Z A" / "Z Z"
        pos += 2
        tokens.append("S")
        pos += 1

    def leaf_tokens(_level: int, row: int) -> list[str]:
        return ["Z", "A" if truth_table[row] == "1" else "Z", "END@"]

    def node(level: int, zero: list[str], one: list[str], at: int) -> list[str]:
        # ``Z``, the level's ``A`` run, ``L``, ``C`` and the ``ONE@`` slot all
        # precede the subtrees, which is the node's own width; the one subtree
        # therefore starts a further ``len(zero)`` along, 1-based.
        return [
            "Z",
            *("A" for _ in range(perm[level])),
            "L",
            "C",
            f"ONE@{at + width(level) + len(zero) + 1}",
            *zero,
            *one,
        ]

    # Every tree token is one command (unlike the load block's ``{Xi}``, which
    # expands to two), so the tree's command count is its token count.
    tree = decision_tree_tokens(
        truth_table,
        leaf_tokens,
        node,
        parent_width=width,
        start=pos,
        collapse=True,
    )
    tokens += tree
    end = pos + len(tree) + 1  # 1-based goto operand just past the last command
    return " ".join(
        str(end) if t == "END@" else str(int(t[4:])) if t.startswith("ONE@") else t
        for t in tokens
    )


def minsky_swap(truth_table: str) -> str:
    """Build a Minsky Swap template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Minsky Swap has no input command, so this is a parameterized generator:
    the template's ``{Xi}`` placeholders become *fixed-length* setters that
    assemble the input's numeric index into ``reg[0]`` — one block per bit,
    so the inputs are embedded exactly ``n`` times.  Each non-LSB bit's block
    is ``2**n`` commands long: ``+`` repeated for its weight followed by
    ``*``-padding to length (both runs are even, so the pointer is restored),
    or ``*``-padding alone for a zero.  The LSB block is the length-4
    ``+*+*`` (adds one, and leaves ``reg[1]`` polluted with a one) or
    ``****`` (a no-op), so the setter length is fixed without an odd pad.

    A cascade of ``2**n`` ``~``s then routes the assembled value *v* to leaf
    *v* — each ``~`` decrements a nonzero register and jumps on zero, so the
    (v+1)-th one sees the value hit zero.  A leaf flips the polluted
    ``reg[1]`` (which holds the LSB) to the answer, then ``~``s on the
    (zeroed) ``reg[0]`` to run off the program end, so the dumped registers
    read ``0 {answer}``.
    """
    n = _validate_truth_table(truth_table)

    tokens: list[str] = []
    targets: list[int] = []
    pos = 0  # instantiated command index of the next command

    # load: bits MSB first; every non-LSB setter is a length-2^n block, the
    # LSB a length-4 block
    for i in range(n - 1):
        tokens.append("{X" + str(i) + "}")
        pos += 2**n
    tokens.append("{X" + str(n - 1) + "}")
    pos += 4

    for _ in range(2**n):  # cascade: route the assembled value to leaf v
        tokens.append("~")
        targets.append(0)
        pos += 1
    for v in range(2**n):  # leaves: reg[1] holds the LSB; make it the answer
        targets[v] = pos + 1
        tokens.append("*")  # pointer onto reg[1]
        pos += 1
        lsb = v & 1
        if lsb == 1 and truth_table[v] == "0":
            tokens.append("~")  # reg[1] is 1 here, so it decrements, no jump
            targets.append(0)
            pos += 1
        elif lsb == 0 and truth_table[v] == "1":
            tokens.append("+")
            pos += 1
        tokens.append("*")  # pointer back onto reg[0]
        pos += 1
        tokens.append("~")  # reg[0] is 0, so this always jumps to the end
        targets.append(0)
        pos += 1

    end = pos + 1  # 1-based target just past the last command
    return (
        " ".join(tokens) + "\n" + " ".join(str(end if t == 0 else t) for t in targets)
    )


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
# halt-vs-hang ring (see ``docs/walls.md``).
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
# A one bit's block used to be its ``~`` and nothing else, where a zero
# bit's is a dense box, so ``_compact`` dropped the one's blank rows and the
# emitted program's size counted the ones: at n == 2 the four programs came
# out 123, 110, 110, and 97 characters.  The one blocks now carry inert
# walls sized so each block's glyphs occupy the same number of characters as
# the zero block it stands against (18 for the first, 14 for the rest).
#
# What a row costs is ``len(row.rstrip())``, so what matters is the column
# its *last* glyph sits in -- a row needs one wall, not a run of them, and
# the blanks to its left are paid for either way.  That holds for the ``~``
# rows too: leading blanks hold the ``~`` at column 3 just as well as glyphs
# would, so the row is a bare ``~`` with one wall past it.
#
# ``*`` turns the IP clockwise, so a wall is only inert where the IP cannot
# reach it.  The IP enters the header at (0, 0) heading right and crosses
# columns 0-2 of that row to reach its ``*``, so the first block's row 0 is
# left exactly as it was; every cell walled here is one no run visits.
_FIRST_ONE = ["   *", "   ~*", "  *", "  *", "  *"]
_FIRST_ZERO = ["   *", "*~* ", "*  *", "*  *", "* * "]
_NEXT_ONE = ["   ~*", "  *", "  *", "  *"]
_NEXT_ZERO = ["*~* ", "*  *", "*  *", "* * "]

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
    header = ["{X0}"]
    header.extend(["    "] * 4)
    for i in range(1, n):
        header.append("{X" + str(i) + "}")
        header.extend(["    "] * 3)
    rows = header + _MIDDLE + _tree(list(truth_table))
    return "\n".join(row.rstrip() for row in rows)


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


def home_row(truth_table: str) -> str:
    """Build a Home Row template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Home Row has no input command, so this is a parameterized generator:
    each ``{Xi}`` placeholder becomes a two-character setter at a bit cell
    that the harness fills in per instantiation.  The cell is zero when the
    placeholder is reached, so the setter raises it with ``a`` and then
    either clears it again (``s``) or leaves it (``j``, whose skip does not
    fire on the now-nonzero cell), spending the same width either way.

    Unlike the removed ``n <= 2``
    routing generator (which tried to send the beam to one of ``2**n``
    distinct leaf cells -- a wall past ``n == 2`` on the fixed 5x5 grid),
    this closed-form construction packs the bits into a single binary
    accumulator and then walks a linear chain of leaf checks, so it never
    needs more than a handful of live cells regardless of ``n``.

    A cell holds the current value under test; the setup line seeds a
    second cell with the ASCII digit base (``48``, ``'0'``).  Each of the
    ``n`` bit-packing lines is ``{Xi} l s ffff a{2**(n-1-i)} f l``: the
    ``l``/``s``/``l`` triple is Home Row's position-stable "run once iff
    nonzero, consuming the guard" gate (loops cannot nest -- ``l``s pair
    strictly by order of appearance -- so this gate, not a BF-style bracket
    match, is what makes the packing safe to chain), and its body adds the
    bit's binary weight to the accumulator only when the bit is 1. After
    all ``n`` gates the accumulator holds the combination's integer index
    ``0 .. 2**n - 1``.

    The remaining ``2**n`` lines are a linear equality chain, one per
    index ``k``: ``a ffff l s f s ff l f l f <answer> k ; l f f`` fans the
    accumulator out into a working copy and a backup (destroying the
    accumulator), subtracts ``k`` from the working copy via the leading
    ``a ffff``/``s`` structure, and the position-stable gate on that
    difference either prints the baked answer byte and halts (a match) or
    restores the accumulator from the backup and falls through to test
    ``k + 1``.  The answer byte is a literal ``a`` (or nothing) baked
    directly from ``truth_table[k]`` -- unlike the ``n`` input bits, it is
    known at generation time, not supplied by the harness, so it needs no
    ``{Xi}`` placeholder.  The final line (index ``2**n - 1``) needs no
    restore, since every other index has already been ruled out.
    """
    n = _validate_truth_table(truth_table)
    setup = "aaaaaalsffaaaaaaaaffflf"
    bit_lines = [
        "{X" + str(i) + "}lsffff" + "a" * (2 ** (n - 1 - i)) + "fl" for i in range(n)
    ]
    leaves = [
        "afffflsfsfflflf" + ("a" if bit == "1" else "") + "k;lff"
        for bit in truth_table[:-1]
    ]
    leaves.append("f" + ("a" if truth_table[-1] == "1" else "") + "k;")
    return setup + "".join(bit_lines) + "".join(leaves)
