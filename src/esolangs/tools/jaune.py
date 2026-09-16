"""Boolean-function generators for Jaune and its multiply dialect."""

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
    stored_inputs,
)

# ROTfuck rotates the whole program after every command, so a brainfuck-style
# decision tree does not survive: the bracket that fires seeks its partner in
# the *rotated* program, at a rotation state that depends on the step count.
# The construction below is the discovered escape, verified against the
# interpreter: each ``[`` body is a *straight-line* ``+-><``-only block (no
# brackets), and the closing ``]`` is a phantom character whose position is
# encoded so that the ``[``-fire seek finds it at the right rotation state.
#
# A block is ``[ body ]`` at positions ``p``..``q`` where ``len(body)``
# satisfies ``len(body) + 1 ≡ 0 (mod 8)``:
#
# - skip path (cell == 0): the ``[`` fires, rotates once, seeks forward for
#   ``]`` at depth 1, and lands at ``q + 1`` with rotation state ``p + 1``;
# - body path (cell != 0): the body runs (straight-line, pointer starts and
#   ends on the tested cell, which stays nonzero), and at ``q`` the phantom
#   shows ``rot^len(body)(']')`` = ``'['`` (since ``len(body) ≡ 7``), which
#   does not fire on the nonzero cell, so it advances to ``q + 1`` with state
#   ``q + 1 ≡ p + 1 (mod 8)``.
#
# Both paths therefore re-converge at ``q + 1`` in the same rotation state,
# so the rest of the program can be encoded position-wise.  A body command at
# relative offset ``j`` must also satisfy ``rot^{-j}(cmd)`` not a bracket, so
# the ``[``-fire seek (at state ``p + 1``) sees no bracket inside the body.
#
# The generator is a branch-free minterm sum over an idempotent-zeroing
# indirection: each input bit ``b_i`` (cell ``i``) and its complement ``c_i``
# (cell ``n + i``, set to 1) guard blocks that count mismatches into cells
# ``mc_k``; one block per minterm then zeroes ``m_k`` (cell
# ``2n + 1 + 2**n + k``) iff ``mc_k != 0``, so ``m_k == 1`` exactly when the
# input is ``k``; and blocks guarded by the ``1``-rows accumulate into the
# result cell, which is printed as ``48 + r``.


def jaune(truth_table: str) -> str:
    """Build a Jaune program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    All ``n`` bits are read up front -- one ``v`` each (a digit character,
    ``ord-48``) -- and the tree then routes with ``?`` jumps: a node walks to
    the cell holding its bit and ``N?`` jumps to label ``N`` when that cell is
    nonzero, else falls through.  Each leaf prints its answer with ``^`` and
    terminates locally.  A subtree whose table slice is a constant
    collapses to a single leaf.

    Only the inputs the tree actually branches on get a cell of their own:
    a read is followed by ``>`` when its bit is needed later and left to be
    overwritten by the next read when it is not, so the kept bits sit in one
    contiguous block and the tree navigates a span as wide as the function's
    real dependencies.  A leaf then prints from the cell it is standing on
    -- its parent's test cell, whose value it knows -- so the answer costs
    at most one ``+``/``-`` and no navigation.

    **Reading up front is what makes the input count constant.**  The reads
    used to sit *at* the nodes, so a folded tree skipped them: a constant
    table consumed no input at all while a parity table consumed every bit,
    making the program's stream consumption a function of its truth table.
    Every generator here must avoid this -- the reads are
    the interface -- and Jaune escaped the contract test that sweeps for it
    only by not being registered in ``BY_FUNCTION``.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.helpers.best_input_order`),
    which the hoist enables: with every bit parked in its own cell, a node
    can test any of them.  Navigation costs one ``>``/``<`` per cell
    crossed, so an order pays for the folds it wins, and the search measures
    rather than assumes.
    """
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _jaune_ordered)
    return _jaune_linear(truth_table)


def _jaune_linear(truth_table: str) -> str:
    """Emit a linear spatial table and travelling counter for Jaune."""
    n = _validate_truth_table(truth_table)
    out = ["v>" * n]

    # Cell n is counter 0; each row then owns one output cell and the next
    # counter cell.  Only one increment is needed for a true row.
    for bit in truth_table:
        out.append(">")
        if bit == "1":
            out.append("+")
        out.append(">")
    out.append("<" * (n + 2 * len(truth_table)))

    # Revisit each input, carry it in the hold cell, and add its unary weight
    # to counter 0.  The weights sum to T-1.
    for i in range(n):
        out.append("#")
        out.append(">" * (n - i))
        out.append("&" * (1 << (n - 1 - i)))
        if i + 1 < n:
            out.append("<" * (n - i - 1))

    # Move a decremented copy of the counter two cells at a time.  When it
    # reaches zero, the adjacent cell is the selected output.
    out.append("1:2!#>>%&-1?1!2:>^.")
    return "".join(out)


def _jaune_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Jaune program; see :func:`jaune`.

    Two things keep this cheap, and both come from the tree's shape being
    known before a line is emitted.

    **Inputs the tree never tests are clobbered rather than stored.**  The
    read contract asks that every input be *consumed*, not that every value
    be *kept*, so an input no node branches on is read into the cell the
    next read overwrites -- ``v`` without the following ``>``.  The tested
    bits then land in adjacent cells, so the tree navigates a block as wide
    as the function's real dependencies rather than one as wide as ``n``.  A
    constant table reads every input and stores none.

    **A leaf prints from the cell it is already standing on.**  It was
    reached by its parent's test, so the pointer is on that parent's cell
    and the value there is known -- 1 on the then-branch, 0 on the else --
    which makes the leaf one ``+``/``-`` and a ``^`` with no navigation at
    all.  Mutating a bit cell is safe because exactly one leaf runs per
    execution and it terminates immediately.

    The pointer's position on entry to a node is a function of its *level*
    alone, never of the path taken: both of a parent's branches leave the
    pointer on the parent's cell, so the navigation is computed per level
    instead of threaded through the branch history.
    """
    n = _validate_truth_table(truth_table)
    label = [1]
    constant = constant_span_test(truth_table)

    def fresh() -> int:
        label[0] += 1
        return label[0]

    def move(frm: int, to: int) -> str:
        return ">" * (to - frm) if to >= frm else "<" * (frm - to)

    stored = stored_inputs(truth_table, perm)
    # Reads run in input order; only a stored input advances the pointer, so
    # the kept bits occupy a contiguous block from cell 0.
    cell_of: dict[int, int] = {}
    reads = ""
    slot = 0
    for i in range(n):
        reads += "v"
        if i in stored:
            cell_of[i] = slot
            slot += 1
            reads += ">"
    # A clobbered read leaves its value under the pointer, so the cell the
    # reads finish on is blank only when the last read advanced off it.  A
    # whole-table constant prints from there and needs it zero, so step once
    # more when the final read clobbered -- and the entry cell moves with it.
    scratch = slot
    if n and (n - 1) not in stored:
        reads += ">"
        scratch = slot + 1

    def leaf(value: str, held: int | None) -> str:
        want = int(value)
        have = 0 if held is None else held
        adjust = "+" * (want - have) if want >= have else "-" * (have - want)
        return adjust + "^."

    def node(level: int, lo: int, hi: int, entry: int, held: int | None) -> str:
        if level == n or constant(lo, hi):
            return leaf(truth_table[lo], held)
        # A clobbered input has no cell to test.  Its bit cannot change the
        # answer, so the two halves of this span are value-identical and
        # descending into either one is the same function -- take the zero
        # half, which keeps the row span halving in step with the level.
        if perm[level] not in cell_of:
            return node(level + 1, lo, (lo + hi) // 2, entry, held)
        cell = cell_of[perm[level]]
        then_lbl = fresh()
        mid = (lo + hi) // 2
        then = node(level + 1, mid, hi, cell, 1)
        else_ = node(level + 1, lo, mid, cell, 0)
        return move(entry, cell) + f"{then_lbl}?{else_}{then_lbl}:{then}"

    return reads + node(0, 0, 2**n, scratch, None)


def jaune_multiply() -> str:
    """Build a Jaune program reading two decimal numbers and printing their product.

    The program reads decimal digits (most-significant first, one per input
    line) into the first operand until a ``*`` line, then digits into the
    second operand until a ``#`` line, and prints the product as a decimal
    number with no leading zeros.  The single construction handles *any*
    number of digits, so the generator takes no ``n`` parameter: multiplying
    is one function ``a * b``, and the operand lengths are a property of the
    input, not of the function (unlike a boolean truth table, where ``n``
    selects a different function space).

    Jaune is the language the multiply capability needs: its cells do not
    wrap (the author's JauneJS stores each cell as a JavaScript number with
    plain ``+=``/``-=``, and this interpreter uses Python ``int``), so each
    operand fits in a single cell with no digit-per-cell carry, and ``^``
    prints the current cell as a decimal number directly.  Each read loop
    runs on a dedicated always-one
    cell: the ``?``/``!`` jumps are conditional, so a cell permanently set to
    1 gives the loop-back jump an unconditional trigger (the sentinel check
    is the only exit).  A digit is folded into the operand with ``v+`` (read
    a digit and add it), ``#`` (copy the current cell to hold) and a run of
    nine ``&`` (add the hold cell), which multiplies the accumulated value by
    10; a sentinel is detected by adding its offset from a digit (``*`` is
    42, so ``6+`` zeroes it) and jumping on zero.  The product is then a
    repeated-addition loop over the second operand.  Cells 0/1/2/3/4 hold
    the first operand, the digit scratch, the second operand, the result,
    and the always-one trigger.
    """
    out: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        while pos < target:
            out.append(">")
            pos += 1
        while pos > target:
            out.append("<")
            pos -= 1

    def cmd(s: str) -> None:
        out.append(s)

    move(4)
    cmd("1+")  # cell 4 = 1: the unconditional loop-back trigger
    # read the first operand until '*': label 1 at cell 4
    cmd("1:")
    move(1)
    cmd("v")
    cmd("6+")  # '*' is 42, so ord-48 == -6; +6 zeroes it
    cmd("2!")  # a zero (the sentinel) exits to label 2
    cmd("6-")
    move(0)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(0)
    cmd("&")
    move(4)
    cmd("1?")  # always jump back to label 1
    cmd("2:")  # first operand done; the '*' was read at cell 1
    pos = 1
    move(4)
    # read the second operand until '#': label 4 at cell 4
    cmd("4:")
    move(1)
    cmd("v")
    cmd("13+")  # '#' is 35, so ord-48 == -13; +13 zeroes it
    cmd("3!")  # a zero (the sentinel) exits to label 3
    cmd("13-")
    move(2)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(2)
    cmd("&")
    move(4)
    cmd("4?")  # always jump back to label 4
    cmd("3:")  # second operand done; the '#' was read at cell 1
    pos = 1
    move(2)
    # multiply: while cell 2 != 0: cell 3 += cell 0; cell 2 -= 1
    cmd("5:")
    cmd("6!")
    move(0)
    cmd("#")
    move(3)
    cmd("&")
    move(2)
    cmd("1-")
    cmd("5?")
    cmd("6:")
    pos = 2
    move(3)
    cmd("^")
    cmd(".")
    return "".join(out)
