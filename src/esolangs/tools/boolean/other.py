"""Boolean-function generators for languages in the ``other`` category."""

# abcdirection, streetcode, and ztoalc_l_boolean each own a file because
# their construction (a grid layout or a program search) dwarfs the rest of
# the category; they are re-exported here so this module stays the import
# site the package and tests already use.
from esolangs.tools import laserfuck_layout
from esolangs.tools.boolean.abcdirection import abcdirection
from esolangs.tools.boolean.helpers import _maybe_complement, _validate_truth_table
from esolangs.tools.boolean.streetcode import streetcode
from esolangs.tools.boolean.ztoalc_l import ztoalc_l_boolean

__all__ = [
    "abcdirection",
    "between",
    "bit_tilde",
    "clockwise",
    "container",
    "forbin_boolean",
    "laserfuck",
    "nevermind",
    "streetcode",
    "suptiftam",
    "taglate",
    "three_x",
    "ztoalc_l_boolean",
]

# Closed-form 3x constant encodings.  Every integer is built from the literal
# 3 with the ``x`` op (which replaces the top three items ``a, b, c``, c on
# top, with ``(c-b)//a``).  The three base-3 digits are:
_ZERO = "333x"  # (3-3)//3 = 0
_ONE = "3333x3x"  # (3-0)//3 = 1
_TWO = _ONE + _ONE + "3x"  # (3-1)//1 = 2

# From [v], ``push X # push Y x`` leaves [(Y-v)//X], so with X=-1/3 and
# Y=-d/3 it maps v -> (-d/3 - v)/(-1/3) = 3v + d.  These are the two fixed
# rationals (and the d=0 case, which is just 0):
_NEG_THIRD = "3" + _ONE + _ZERO + "x"  # (0-1)//3 = -1/3
_NEG_TWO_THIRDS = "33" + _ONE + "x"  # (1-3)//3 = -2/3
_DIGIT = (_ZERO, _ONE, _TWO)
_NEG_DIGIT = (_ZERO, _NEG_THIRD, _NEG_TWO_THIRDS)


def _const(n: int) -> str:
    """3x code pushing ``n`` on a clean stack, for any integer ``n``.

    ``n`` is written in base 3 and its digits are processed most significant
    first: ``v`` starts as the leading digit and each following digit ``d``
    applies the affine map ``v -> 3v + d`` via one ``x`` (see ``_NEG_THIRD``).
    The result is a closed-form program of ``O(log_3 n)`` length that leaves
    exactly ``[n]`` on the stack.
    """
    if n <= 2:
        return _DIGIT[n]
    digits = []
    while n:
        digits.append(n % 3)
        n //= 3
    prog = _DIGIT[digits[-1]]
    for d in reversed(digits[:-1]):
        prog += _NEG_THIRD + "#" + _NEG_DIGIT[d] + "x"
    return prog


def myscript(truth_table: str) -> str:
    """Build a MyScript program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program reads all ``n`` input lines up front into ``b0..b(n-1)``,
    then walks a ``check`` decision tree: at level ``i`` it branches on
    ``b_i`` and the leaves ``say`` the table value for the combination.
    """
    n = _validate_truth_table(truth_table)
    lines = [f"var b{i} is ask" for i in range(n)]

    def build(i: int, combo: int, pad: str) -> list[str]:
        if i == n:
            return [f'{pad}say "{truth_table[combo]}"']
        one = build(i + 1, combo | (1 << (n - 1 - i)), pad + "    ")
        zero = build(i + 1, combo, pad + "    ")
        return [
            f"{pad}check b{i}?",
            f'{pad}  if "1",',
            *one,
            f"{pad}  else,",
            *zero,
        ]

    return "\n".join(lines + build(0, 0, ""))


def three_x(truth_table: str) -> str:
    """Build a 3x program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    3x reads an integer with ``?`` and has no direct boolean literals or
    conditionals, so the generator builds a decision tree with variables:

    - each ``?`` reads one input bit and stores it in a variable (the
      cheapest names after 0 and 3);
    - a ``( ... )`` loop runs while its guard is nonzero: the guard value is
      popped into a trash variable (0), the body stores the table entry into
      the result variable (3), and a sentinel zero exits the loop.

    The result variable defaults to the majority table value (so the
    ``( ... )`` loop emits no override at all when every row matches), and
    only the input combinations whose table entry differs from the default
    get an override block.  Each override's ``( ... )`` guard leaves the
    stack balanced via the trash pop, so arbitrary ``n`` works.
    """
    n = _validate_truth_table(truth_table)

    # Variable allocation: var 0 is the loop-trash (its constant, 333x, is
    # short and emitted twice per guard), var 3 is the result (its constant
    # is the single char `3`, emitted once per table entry), and the inputs
    # live in the cheapest remaining names by actual constant length (the
    # base-3 encodings are non-monotonic: 15 is cheaper than 13).  Every
    # input is read once per override block, so any assignment of the n
    # cheapest names to the inputs costs the same.
    trash = _const(0) + "#v"  # pop the stack top into variable 0
    result = 3
    used = {0, 3}
    input_vars = sorted(
        (v for v in range(3 + n) if v not in used),
        key=lambda v: len(_const(v)),
    )[:n]

    def store(var: int) -> str:
        return _const(var) + "#v"  # var = stack top, stack ends empty

    def read(var: int) -> str:
        return _const(var) + "^"

    def not_bit() -> str:
        return _ONE + "#" + _ONE + "x"  # from [b] leave [1-b]

    def guard(i: int, body: str) -> str:
        """If bit i is 1, run ``body``; leaves the stack balanced."""
        return read(i) + "(" + trash + body + _ZERO + ")" + trash

    def guard_not(i: int, body: str) -> str:
        """If bit i is 0, run ``body``; leaves the stack balanced."""
        return read(i) + not_bit() + "(" + trash + body + _ZERO + ")" + trash

    prog = "".join("?" + store(v) for v in input_vars)

    # Default the result to the majority value so only the minority rows
    # need an override block (combos matching the default are skipped).
    default = "1" if truth_table.count("1") >= truth_table.count("0") else "0"
    prog += (_ONE if default == "1" else _ZERO) + store(result)

    # One decision tree instead of an independent guard chain per differing
    # combo: rows that share a bit prefix share the guards for that prefix,
    # amortizing the ~19-char guard scaffolding across them.  Each guard
    # leaves the stack balanced, so both branches concatenate safely inside
    # their parent's body, and whole subtrees that match the default are
    # pruned.
    def override(combo: int) -> str:
        return (_ONE if truth_table[combo] == "1" else _ZERO) + store(result)

    def build(rows: list[int], depth: int) -> str:
        if not rows:
            return ""
        if depth == n:
            return override(rows[0])  # rows are pruned, so it differs from default
        bit = n - 1 - depth
        rows1 = [r for r in rows if (r >> bit) & 1]
        rows0 = [r for r in rows if not (r >> bit) & 1]
        sub1 = build(rows1, depth + 1)
        sub0 = build(rows0, depth + 1)
        return (guard(input_vars[depth], sub1) if sub1 else "") + (
            guard_not(input_vars[depth], sub0) if sub0 else ""
        )

    differing = [c for c in range(2**n) if truth_table[c] != default]
    prog += build(differing, 0)

    prog += read(result) + "!"
    return prog


def nevermind(truth_table: str) -> str:
    """Build a Nevermind program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Nevermind reads each input with ``input,?`` into its own variable, then a
    decision tree of nested ``if``/``endif`` blocks prints the result for the
    matching combination.
    """
    n = _validate_truth_table(truth_table)
    lines: list[str] = []
    for i in range(n):
        lines.append("input,?")
        lines.append(f"make,{chr(ord('a') + i)},$answer")

    def build(k: int, row: int) -> None:
        if k == n:
            lines.append(f"print,{truth_table[row]}")
            return
        for bit in (0, 1):
            lines.append(f"if,${chr(ord('a') + k)},==,{bit}")
            build(k + 1, row * 2 + bit)
            lines.append("endif")

    build(0, 0)
    return "\n".join(lines)


def _reorder_tt(tt: str, n: int) -> str:
    """Reorder truth table entries into the slot order the reduces expect.

    Each entry sits in a value slot ``[0, s_i, 0, s_j, ...]``; an even
    reduce must be able to drop an entire contiguous run of slots without
    splitting a pair.  Sorting the input index ``i`` by ``(-(i >> 1),
    i & 1)`` puts the 1-group of the current input first, then the 0-group,
    with the two sub-cases of the next input adjacent inside each group.
    Odd-reduce levels (which branch the other way) then re-apply the same
    ordering, so the sort key serves both.
    """
    indices = sorted(range(2**n), key=lambda i: (-(i >> 1), i & 1))
    return "".join(tt[i] for i in indices)


def _even_reduce(pairs: int, level: int, n: int) -> str:
    """Even-reduction block: select half the value pairs, keep all inputs.

    The queue holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then
    two 48s, then the ``n`` input chars.  The ``rot`` rotation brings the
    next input to the front; ``gy ... gz`` branches on it so the ``e^pairs``
    strides past the half of the value slots the input rejects; ``e^ahead``
    skips the untouched half and ``f^pairs`` drops it.  Every input stays on
    the queue, so the level that follows still sees all ``n`` of them.
    """
    processed = level
    ahead = n - level
    total = n
    rot = 2 * pairs + 2 + processed
    return (
        "e" * rot
        + "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )


# Final odd-reduce block: the committed n==2 pattern.  Given the 8-cell
# queue [0, v0, 0, v1, 48, 48, prev, curr] (v0/v1 the two candidate values,
# prev/curr the two remaining inputs), it rotates curr and prev to the front,
# drops the candidate the inputs reject, adds the surviving value to one of
# the two 48s (48 + bit), and prints it with ``i``.
_SEL1_N2: str = (
    "e" * 7
    + "gy"
    + "e" * 3
    + "gz"
    + "e" * 3
    + "gy"
    + "e" * 3
    + "gz"
    + "ff"
    + "gy"
    + "e" * 4
    + "gz"
    + "e"
    + "a"
    + "e" * 4
    + "i"
)


def _build_padded_tt(truth_table: str, n_effective: int) -> str:
    """Pad a ``2**(n_effective - 1)``-entry truth table to ``n_effective`` bits.

    Odd ``n`` is computed with ``n_effective = n + 1`` inputs whose leading
    (ghost) digit is always 0.  The real table covers the ghost=0 half; the
    entries the ghost=1 would select are padded with 0 so the never-taken
    rows stay harmless.
    """
    half = 2 ** (n_effective - 1)
    return truth_table.ljust(half * 2, "0")


def between(truth_table: str) -> str:
    """Build a Between program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program reads each input bit as a line, converts it to an integer
    with ``c``, then walks a decision tree laid out linearly: every node
    tests bit ``i`` and, when the bit is zero, jumps over the ``1`` subtree
    to the ``0`` subtree; each leaf prints ``|0|``/``|1|`` and exits.  The
    branch addresses are 0-indexed line numbers, so the size of each subtree
    is computed ahead of the linear layout.
    """
    n = _validate_truth_table(truth_table)

    def leaf_value(path: list[int]) -> int:
        row = 0
        for bit in path:
            row = row * 2 + bit
        return int(truth_table[row])

    def size(path: list[int]) -> int:
        if len(path) == n:
            return 2
        return 1 + size([*path, 1]) + size([*path, 0])

    lines: list[str] = []
    for bit in range(n):
        lines.append(f"'{bit}'v.")
        lines.append(f"[{bit}]i.")
        lines.append(f"[{bit}]s|[{bit}]c.|")

    def emit(path: list[int], offset: int) -> int:
        if len(path) == n:
            lines.append(f"|{leaf_value(path)}|p.")
            lines.append(".x.")
            return offset + 2
        zero_addr = offset + 1 + size([*path, 1])
        lines.append(f"|{zero_addr}|f([{len(path)}]=|0|)")
        offset += 1
        offset = emit([*path, 1], offset)
        return emit([*path, 0], offset)

    emit([], len(lines))
    return "\n".join(lines)


def laserfuck(truth_table: str, width: int | None = None) -> str:
    r"""Build a LaserFuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The laser starts at ``o`` with a random heading, so a mirror funnel
    (``|``/``^``/``_`` plus two ``}`` on the row above) sends every heading to
    the top row moving right.  There it reads ``n`` bits into cells 0..n-1
    (each ``,`` then 48 ``-`` normalizes ``'0'``/``'1'`` to 0/1) and enters a
    decision tree.  Each node at level ``i`` moves the pointer to cell ``i``,
    then lays down ``#`` ``v`` ``)`` ``\\``: the ``#`` skips the ``v`` on
    approach, ``)`` routes a zero cell through to ``\\`` (down column c+3) and
    a nonzero cell back to ``v`` (down column c+1); each child row's ``\\``
    turns the beam right into the child.  Leaves (one per input combination,
    at a dedicated high column so no ``+`` run crosses a descent column)
    retire the input cells, move the pointer to cell ``n``, set it to the
    result, and hit ``x`` to halt.

    LaserFuck has no output instruction: it prints the tape when the last
    laser dies.  Two properties of that dump make the program print its
    answer and nothing else.

    The dump has two modes, and this generator uses the default *decimal*
    one, which prints each cell as a number.  (A ``\\xff`` in the first grid
    cell would select byte mode instead, where the answer would come out as
    the character ``chr(result)``; the generator used to do that and pay 48
    ``+`` per leaf to reach ASCII ``'0'``/``'1'``.)  So a leaf writes the
    result itself -- one ``+`` for a one, and ``+-`` for a zero, since a cell
    has to be *touched* to be dumped at all and leaving it alone would print
    nothing.

    The dump also skips any cell holding a negative value, which is how the
    input cells are hidden.  A leaf knows the whole input combination, so it
    subtracts one more than each bit's value on its way past -- driving cell
    ``i`` to ``-1`` whatever it held -- before walking up to the answer cell.

    The tree is loop-free, so no loop-ring geometry is needed.

    ``width`` bounds the columns.  Unfolded, the grid is dominated by its
    straight runs -- the ``n`` input readers are 49 columns each and every
    leaf is another 49 -- which is why a three-input table is 253 columns
    wide while its decision tree spans only 42.  With a width, each of those
    runs is folded into a zigzag by
    :func:`~esolangs.tools.laserfuck_layout.fold` and costs rows instead:
    the readers fold into a band before the tree, and each leaf folds into a
    band of its own below it.  The tree itself is never
    folded, since its columns carry the descent paths that make the program
    correct; it grows six columns per node, so a width narrower than the
    tree needs cannot be met and the grid comes out as wide as the tree.
    """
    n = _validate_truth_table(truth_table)
    # Every leaf needs a drop corridor of its own, and they take the
    # rightmost columns inside the width; the folded runs get what is left.
    # A fold only makes progress if that leaves room for the margin, at
    # least one op, and the turn-down, so too narrow a width is ignored.
    fold_width = (width or 0) - 2**n - 1
    folded = width is not None and fold_width >= laserfuck_layout.MIN_WIDTH
    rows: int = 2 ** (n + 1) - 1
    total_cols: int = 3 + 49 * n + (2 ** (n + 1) - 1) * 6 + 2 + 49 + 8

    if folded:
        # A fold trades columns for rows, so a folded grid needs many more of
        # them than the tree alone does.
        def bands(run: int) -> int:
            return laserfuck_layout.rows_needed(run, fold_width)

        readers_len = 49 * n  # ',' + 48 '-' per input, '>' between them
        rows += bands(readers_len) + 2  # +2 for the turn onto the tree's row
        # each leaf: its drop row, then its own folded band
        rows += sum(bands(49 + int(bit)) + 2 for bit in truth_table)
        total_cols = max(total_cols, (width or 0) + 2)
    grid = [[" "] * total_cols for _ in range(rows)]

    # the funnel: every heading ends up on row 0 moving right.  Cell (0, 0)
    # is deliberately blank: a '\xff' there would select byte output mode,
    # and this generator wants the default decimal mode (see the docstring).
    grid[0][1] = "}"
    grid[0][2] = "}"
    grid[1][0] = "|"
    grid[1][1] = "o"
    grid[1][2] = "^"
    grid[2][1] = "_"

    # read n bits into cells 0..n-1 on row 0 (pointer ends at cell n-1).
    # Unfolded these run straight along row 0; folded, they are laid as a
    # zigzag below (see the fold that follows), and the tree starts after it.
    col = 3
    if not folded:
        for i in range(n):
            grid[0][col] = ","
            col += 1
            for _ in range(48):
                grid[0][col] = "-"
                col += 1
            if i < n - 1:
                grid[0][col] = ">"
                col += 1

    # Folded: the readers are laid as a zigzag *before* the tree, and the
    # tree starts on the row the zigzag ends on, so the beam runs straight
    # out of the last reader segment into the root.  The readers are one
    # long straight run -- ',' and 48 '-' per input, '>' between them -- so
    # the fold can break it anywhere.
    base = 0
    if folded:
        readers = ""
        for i in range(n):
            readers += "," + "-" * 48
            if i < n - 1:
                readers += ">"
        base, col = laserfuck_layout.fold(grid, readers, 0, 3, fold_width)
        laserfuck_layout.reserve(grid, base + 2)
        # The tree grows rightwards from wherever the readers stopped, so a
        # long tail on the last reader row would push it past the width no
        # matter how well the runs folded.  Turn down once more instead, so
        # the tree always starts at the margin with the full width to grow
        # into and its span is measured from there.
        grid[base][col] = "v"
        grid[base + 1][col] = "{"
        grid[base + 1][laserfuck_layout.MARGIN] = "v"
        base += 2
        grid[base][laserfuck_layout.MARGIN] = "}"
        col = laserfuck_layout.MARGIN + 1

    # node rows: breadth-first, the root on the row the readers ended on
    # and children on lower rows
    def row(i: int, j: int) -> int:
        return base + int(2**i + j - 1)

    # internal-node columns (preorder); leaves get a dedicated high region
    cols: dict[tuple[int, int], int] = {}
    next_col = [col + 1 + n]  # room for the root's pointer-move cells

    def assign_col(i: int, j: int) -> int:
        if (i, j) in cols:
            return cols[(i, j)]  # pragma: no cover - a tree node is never revisited
        c = next_col[0]
        cols[(i, j)] = c
        next_col[0] = c + 6
        if i < n - 1:
            assign_col(i + 1, 2 * j)
            assign_col(i + 1, 2 * j + 1)
        return c

    assign_col(0, 0)
    leaf_base = next_col[0] + 4  # past every internal column and descent column
    if folded:
        laserfuck_layout.reserve(grid, row(n, 2**n - 1) + 2)

    # leaves: one per input combination on its own row, all at the same
    # high column (past every internal node and descent column), so the
    # grid needs room for just one leaf rather than one per combination.
    #
    # A folded leaf cannot zigzag straight down from its own row: the rows
    # below it belong to the other leaves, and a beam dropping through them
    # would run their '+' cells on the way past.  Instead each leaf turns
    # the beam down a *private* column into a band of rows past every other
    # row, and folds there.  Bands are stacked, so each leaf owns its rows.
    #
    # The drop columns are corridors, not code, but they still occupy
    # columns, so they take the rightmost strip *inside* the width and the
    # folded runs stop short of them.  A beam descending a corridor then
    # crosses only the blank cells to the right of every band's content.
    band = row(n, 2**n - 1) + 2
    drop_base = max(leaf_base + 1, fold_width + 1)
    for j in range(2**n):
        r = row(n, j)
        c = leaf_base
        # the beam arrives from the parent's descent column; it first moved the
        # pointer to cell i (level i), so here it is at cell n-1.
        #
        # The leaf knows the whole input combination -- that is what a leaf
        # is -- so it can retire each input cell on the way past.  Cell i
        # holds bit i, and one more '-' than its value drives it to -1,
        # which dump() skips; sweeping n-1 down to 0 clears every input, and
        # the pointer then walks back up to cell n for the answer.
        sweep = ""
        for i in range(n - 1, -1, -1):
            bit = (j >> (n - 1 - i)) & 1
            sweep += "-" * (bit + 1)
            if i:
                sweep += "<"
        sweep += ">" * n
        # A 0 answer still has to be *touched* to be printed at all, so it
        # is written as '+-' rather than left alone.
        run = sweep + ("+" if truth_table[j] == "1" else "+-")
        if folded:
            drop = drop_base + j
            laserfuck_layout.reserve(grid, band + 1)
            grid[r][drop] = "v"
            grid[band][drop] = "{"  # head back to the margin
            grid[band][laserfuck_layout.MARGIN] = "v"
            end_r, end_c = laserfuck_layout.fold(
                grid, run, band + 1, laserfuck_layout.MARGIN + 1, fold_width
            )
            grid[band + 1][laserfuck_layout.MARGIN] = "}"
            grid[end_r][end_c] = "x"
            band = end_r + 2
        else:
            for k, char in enumerate(run):
                grid[r][c + 1 + k] = char
            grid[r][c + 1 + len(run)] = "x"

    # internal nodes: move the pointer to cell i, then '#','v',')','\\'
    for i in range(n):
        for j in range(2**i):
            r = row(i, j)
            c = cols[(i, j)]
            # root arrives with the pointer at cell n-1; a child at level i
            # arrives with it at cell i-1 (its parent tested bit i-1)
            arrival = n - 1 if i == 0 else i - 1
            moves = ">" * (i - arrival) if i >= arrival else "<" * (arrival - i)
            cur = c - len(moves)
            for ch in moves:
                grid[r][cur] = ch
                cur += 1
            grid[r][c] = "#"
            grid[r][c + 1] = "v"
            grid[r][c + 2] = ")"
            grid[r][c + 3] = "\\"
            zero_r = row(i + 1, 2 * j)  # down column c+3
            one_r = row(i + 1, 2 * j + 1)  # down column c+1
            grid[zero_r][c + 3] = "\\"  # turn the down-beam right
            grid[one_r][c + 1] = "\\"  # turn the down-beam right

    lines = ["".join(ln).rstrip() for ln in grid]
    # a folded grid reserves rows in whole bands, so the last band can leave
    # blank rows past the final 'x'; they carry no code and only pad the file
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _odd_reduce(pairs: int, level: int, n: int) -> str:
    """Odd-reduction block: retire one input, reduce, keep the rest.

    ``level`` is the 0-based reduce level (odd here: 1, 3, ...).  The queue
    holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then two 48s,
    then the ``n`` input chars.  Unlike the even reduce, the odd level
    branches on a *retired* (previous) input whose bit has already been
    used, so ``e^rot`` brings that input to the front and the block runs
    ``zero`` (``gy j e^(qlen-1) gz``) to fold it away, ``swap`` (``e gy j
    e^(qlen-2) j gz``) to encode the current input as the ghost cell the
    even-reduce branches on, and ``bring`` (``e^(qlen-1)``) to put the
    value slots back at the front before ``er`` runs the even-reduce body.

    The ZS adds an extra ghost cell at the front, so the even-reduce body
    uses ``ahead = n - level + 1`` instead of ``n - level``.  No input is
    popped; the final ``f^pairs`` in ``er`` drops only the rejected value
    slots.
    """
    processed = level
    ahead = n - level + 1  # +1 for the ghost cell added by the swap
    total = n
    qlen = 2 * pairs + 2 + total
    rot = 2 * pairs + 2 + (processed - 1) if processed > 0 else 0
    zero = "gy" + "j" + "e" * (qlen - 1) + "gz"
    swap = "e" + "gy" + "j" + "e" * (qlen - 2) + "j" + "gz"
    bring = "e" * (qlen - 1)
    er = (
        "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )
    return "e" * rot + zero + swap + bring + er


def taglate(truth_table: str) -> str:
    r"""Build a Taglate program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ``n == 1`` reads the single input with ``h`` and computes the affine
    combination ``base + bit * coeff`` with the ``b``/``c``/``a`` queue
    arithmetic, then prints it.

    For ``n >= 2`` the program is ``seed\\n<commands>``.  The seed holds
    ``n_effective`` literal ``'1'``s (``n_effective - 1`` leading, one
    trailing) around a run of ``'0'``s; the prefix of ``h``/``e``/``b``/
    ``d``/``j`` commands reads ``n_effective`` inputs and interleaves the
    (reordered) truth-table bits into ``[0, s0, 0, s1, 0, s2, ...]`` value
    slots, followed by two 48s and the inputs.  Odd ``n`` prepends a fake
    zero input (ghost digit) so the slot stride lands on a separator, and
    pads the table to ``n_effective = n + 1`` inputs.

    The command list alternates even-reduce blocks (select half the
    value slots on an input bit, keep all inputs) and odd-reduce blocks
    (retire the previous input, swap the current one in, even-reduce).
    Neither reduce pops inputs; ``e^6 f^(n_effective - 2) e^2`` reshapes
    the queue into the 8-cell ``[0, v0, 0, v1, 48, 48, prev, curr]``
    layout, and ``_SEL1_N2`` selects between the last two candidate
    values on the two remaining inputs and prints ``48 + bit``.
    """
    n = _validate_truth_table(truth_table)
    if n == 1:
        base = 48 + int(truth_table[0])
        coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
        seed = "0" + chr(coeff) + chr(base)
        return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"

    # For odd n, prepend a fake zero-input (ghost) to make the stride land
    # on a separator.  n_effective is the number of h-reads and levels.
    if n % 2 == 1 and n > 1:
        n_eff = n + 1
        full_tt = _build_padded_tt(truth_table, n_eff)
    else:
        n_eff = n
        full_tt = truth_table

    seed = "1" * (n_eff - 1) + "0" * (2 ** (n_eff + 2) + 2) + "1"

    ordered = _reorder_tt(full_tt, n_eff)
    selectors = "".join("bd" if c == "1" else "bb" for c in ordered)

    prefix = (
        "he" * (n_eff - 1)
        + "h"
        + selectors
        + "ee"
        + "b" * n_eff
        + "e" * (2 ** (n_eff + 1) + 2)
        + "j" * n_eff
    )

    select_parts: list[str] = []
    for level in range(n_eff - 1):
        pairs = 2 ** (n_eff - level)
        if level % 2 == 0:
            select_parts.append(_even_reduce(pairs, level, n_eff))
        else:
            select_parts.append(_odd_reduce(pairs, level, n_eff))

    if n_eff > 2:
        # Drop the first n_eff-2 already-used inputs, then rotate the
        # remaining two inputs so the queue matches the 8-cell [0, w0, 0,
        # w1, 48, 48, prev, curr] layout that the committed n=2 odd
        # selector (_SEL1_N2) expects.
        select_parts.append("e" * 6 + "f" * (n_eff - 2) + "e" * 2)
    select_parts.append(_SEL1_N2)

    result: str = seed + "\n" + prefix + "".join(select_parts)
    return result


# Cells in a Clockwise leaf: 'S', the seven ';' that print the answer digit
# with the '+' that set their parity, and the 'S+?' exit.  Both digits fit
# in this height -- '0' pads with one extra 'S' -- so every leaf's exit '?'
# lands on the same row, which is what the ring's bottom row assumes.
_CLOCKWISE_LEAF = 14


def clockwise(truth_table: str) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints the result as the ASCII digit ``'0'`` or ``'1'``.

    The program is a decision tree in a closed ring.  ``S`` zeroes the
    accumulator and seven ``.`` reads consume a ``0``/``1`` input char's seven
    bits, leaving its value bit in the accumulator.  At each node a ``?``
    turns the pointer by ``acc`` quarter-turns, so a zero bit continues down
    the spine while a one bit turns right (cw) into a column; three ``R`` in
    an L pattern turn it back down into the next column, at a ``2**(n-k)``
    displacement so each input combination reaches a unique leaf column.

    A leaf prints the answer's seven bits with ``;``, which emits ``acc % 2``,
    so a ``+`` before a ``;`` flips the parity into the bit that position
    needs.  Printing the ASCII digit rather than the bare bit costs almost
    nothing here: ``'0'`` is ``0110000`` and ``'1'`` is ``0110001``, so the
    two leaves differ by a single ``+``.  The leaf then resets and counts up
    to one (``S+``) so the exit ``?`` sees ``acc == 1`` whatever it printed,
    and turns left onto a shared bottom row; an ``S`` after each exit keeps
    passing paths at acc=0 so they do not turn on another leaf's exit.  Both
    leaves are padded to the same height, so every exit lands on that row.
    The row funnels left to the corner ``R`` and up column 0 to halt.
    """
    n = _validate_truth_table(truth_table)
    cells: dict[tuple[int, int], str] = {}
    root = 2 ** (n + 2) + 8

    def place(node: tuple[int, int], ch: str) -> None:
        cells[node] = ch

    def build(bit: int, x: int, y: int, combo: int) -> None:
        if bit == n:
            leaf(x, y, combo)
            return
        place((x, y), "S")
        for i in range(7):
            place((x, y + 1 + i), ".")
        place((x, y + 8), "?")
        build(bit + 1, x, y + 9, combo << 1)  # b=0: continue down
        # b=1: '?' turns right (cw from down) then three R's turn left->down
        xn = x - 2 ** (n - bit)
        place((xn, y + 8), " ")
        place((xn - 1, y + 8), "R")
        place((xn - 1, y + 7), "R")
        place((xn, y + 7), "R")
        build(bit + 1, xn, y + 9, (combo << 1) | 1)

    def leaf(x: int, y: int, combo: int) -> None:
        # Emit the answer as the ASCII digit rather than as the raw bit.
        # Seven ';' print one bit each, most significant first, and each
        # prints acc % 2 -- so a '+' before a ';' is what flips the parity
        # into the bit that position needs.  '0' is 0110000 and '1' is
        # 0110001, which differ only in the last bit, so the two leaves are
        # the same shape apart from one '+'.
        result = int(truth_table[combo])
        code = "S"
        acc = 0
        for bit in format(48 + result, "07b"):
            if acc % 2 != int(bit):
                code += "+"
                acc += 1
            code += ";"
        # A '?' turns by acc quarter-turns and must see exactly 1 to turn
        # left onto the bottom row.  The accumulator is 2 or 3 by now
        # depending on the digit, so reset and count up to 1 rather than
        # tracking it: 'S+' is uniform where a bare '+' would not be.  The
        # extra 'S' pads the shorter leaf so both are _LEAF_HEIGHT cells and
        # every leaf's exit lands on the same row, which the ring's geometry
        # depends on; 'S' on an already-zero accumulator is a no-op.
        code += "S" * (_CLOCKWISE_LEAF - len(code) - 2) + "+?"
        for i, ch in enumerate(code):
            place((x, y + i), ch)

    build(0, root, 1, 0)

    bottom = 1 + 9 * n + _CLOCKWISE_LEAF - 1
    for (x, y), ch in list(cells.items()):
        if ch == "?" and y == bottom:
            place((x - 1, bottom), "S")
    place((0, bottom), "R")
    place((root, 0), "R")

    height = bottom + 1
    width = max(x for (x, y) in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), ch in cells.items():
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = ch
    return "\n".join("".join(row) for row in grid)


def container(truth_table: str) -> str:
    """Build a Container program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Container is a synchronous rule system: every tick each container's value
    becomes ``max(old + sum of deltas of satisfied ``X>=Y``/``X<=Y`` rules,
    0)``, the empty-named container reads a line of input into ``IN`` when it
    turns on, ``PRINT`` outputs ``OUT`` when it turns on, and ``EXIT`` halts
    when its value changes.  There is no per-tick conditional, so the
    generator timestamps everything with the tick counter ``T``:

    * The empty container pulses on even ticks ``0..2(n-1)`` (``+1 T>=2k``,
      ``-2 T>=2k+1``, ``+1 T>=2k+2``), reading one bit per pulse.
    * For each bit ``k``, an armed gate ``A_k`` (65, dipping to 49) and
      ``B_k`` (47, dipping to 48) make ``IN>=A_k`` and ``IN<=B_k`` hold for
      exactly the tick the bit is in ``IN``, testing bit ``k`` once.
    * A survivor per row (initial 1) is killed by ``-1 IN>=A_k`` or
      ``-1 IN<=B_k`` when the corresponding bit mismatches, so exactly the
      matching row's survivor stays 1.
    * At tick ``2n`` a gate ``Gout`` dips to 1, so ``+1 S_r>=Gout`` adds the
      table entry of the surviving row to ``OUT``; ``PRINT`` fires and
      ``EXIT`` halts.
    """
    n = _validate_truth_table(truth_table)

    lines = ["T:", "+1 T>=T"]
    lines.append(":")  # the empty-named container reads input
    lines.append("+1 T>=0")
    lines.append("-2 T>=1")
    for k in range(1, n):
        lines.append(f"+2 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
    lines.append(f"+1 T>={2 * n}")
    lines.append("IN=50:")  # a value no real byte matches
    for k in range(n):
        lines.append(f"A{k}=65:")
        lines.append(f"-16 T>={2 * k}")
        lines.append(f"+32 T>={2 * k + 1}")
        lines.append(f"-16 T>={2 * k + 2}")
        lines.append(f"B{k}=47:")
        lines.append(f"+1 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
        lines.append(f"+1 T>={2 * k + 2}")
    for row in range(2**n):
        lines.append(f"S{row}=1:")
        for k in range(n):
            if (row >> (n - 1 - k)) & 1:
                lines.append(f"-1 IN<=B{k}")
            else:
                lines.append(f"-1 IN>=A{k}")
    lines.append("Gout=2:")
    lines.append(f"-1 T>={2 * n - 1}")
    lines.append(f"+1 T>={2 * n}")
    lines.append("OUT:")
    lines.append(f"+48 T>={2 * n}")
    lines.append(f"-48 T>={2 * n + 1}")
    for row in range(2**n):
        if truth_table[row] == "1":
            lines.append(f"+1 S{row}>=Gout")
    lines.append("PRINT:")
    lines.append(f"+1 T>={2 * n}")
    lines.append("EXIT=1:")
    lines.append(f"-1 T>={2 * n + 1}")
    return "\n".join(lines)


def bit_tilde(truth_table: str) -> str:
    """Build a bit~ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    bit~ is a bit pool with ``{``/``}`` while-nonzero loops.  Each ``)``
    reads an input byte into eight bits (MSB first), so the input bit lands
    at cell ``8i+7`` and cells ``8i+2``/``8i+3`` hold the ``00110000`` byte
    pattern a ``0`` output needs.  Every (input, one-row) pair each minterm
    tests is pre-copied unconditionally into a fresh cell (chained two-dest
    copies so the source survives), complemented when the minterm needs the
    bit zero; the first input-0 copy also consumes the input bit out of cell
    7 so the output window holds a clean 48.  Each ``1`` row of the table is
    then a nested ``{ bit ... }`` test whose innermost body forces the result
    cell to 1, and the result is copied into cell 7 so ``(`` prints ``48 +
    result``.  Dense tables evaluate the complement instead (fewer minterms)
    and flip the output bit once.
    """
    n = _validate_truth_table(truth_table)

    table, use_complement = _maybe_complement(truth_table)

    prog: list[str] = []
    pos = 0

    def move(dst: int) -> None:
        nonlocal pos
        while pos < dst:
            prog.append(">")
            pos += 1
        while pos > dst:
            prog.append("<")
            pos -= 1

    def copy2(src: int, d1: int, d2: int) -> None:
        """Copy ``src`` to ``d1`` and ``d2``, zeroing ``src``."""
        nonlocal pos
        move(src)
        prog.append("{")
        move(d1)
        prog.append("~")
        move(d2)
        prog.append("~")
        move(src)
        prog.append("~")
        prog.append("}")

    for i in range(n):
        if i:
            move(8 * i)
        prog.append(")")
        pos = 8 * i

    scratch = 8 * n
    uses: dict[tuple[int, int], int] = {}
    for i in range(n):
        src = 8 * i + 7
        for k in range(2**n):
            # only one-rows' indicators are used; the first input-0 copy must
            # still run to consume the input bit out of cell 7
            if table[k] != "1" and not (i == 0 and k == 0):
                continue
            c = (k >> (n - 1 - i)) & 1
            use = scratch
            keep = scratch + 1
            scratch += 2
            copy2(src, use, keep)
            src = keep
            if c == 0:
                move(use)
                prog.append("~")
                pos = use
            uses[(k, i)] = use

    result = scratch
    scratch += 1

    def set_result() -> None:
        nonlocal pos
        move(result)
        prog.append("{ ~ } ~")
        pos = result

    def node(level: int, k: int) -> None:
        nonlocal pos
        if level == n:
            set_result()
            return
        use = uses[(k, level)]
        move(use)
        prog.append("{")
        pos = use
        node(level + 1, k)
        move(use)
        prog.append("~")
        pos = use
        prog.append("}")

    for k in range(2**n):
        if table[k] == "1":
            node(0, k)

    move(result)
    prog.append("{")
    move(7)
    prog.append("~")
    move(result)
    prog.append("~")
    prog.append("}")
    pos = result
    if use_complement:
        move(7)
        prog.append("~")
        pos = 7
    move(0)
    prog.append("(")
    return "".join(prog)


def forbin_boolean(truth_table: str) -> str:
    """Build a Forbin program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Forbin's ``in`` reads one bit (most significant first), so each input
    byte contributes 8 reads and only the last bit (the LSB, which is what
    distinguishes ``'0'`` from ``'1'``) is used.  A decision tree over those
    bits is laid out with the range-loop if-trick: ``for _:!b..b`` runs its
    body once when ``b`` is 1 (the ``return`` cuts the second iteration)
    and falls through when ``b`` is 0, so each node emits the 1-subtree then
    the 0-subtree and every leaf prints the result byte and returns.
    """
    n = _validate_truth_table(truth_table)

    lines: list[str] = ["main {"]
    bits: list[str] = []
    for i in range(n):
        reads = [f"i{i}_{j}" for j in range(8)]
        lines.append(f"  {','.join(reads)} = (in 0);")
        bits.append(reads[7])

    def emit(level: int, row: int) -> None:
        if level == n:
            byte = 49 if truth_table[row] == "1" else 48
            lines.append(f"  out {','.join(format(byte, '08b'))};")
            lines.append("  return 0;")
            return
        lines.append(f"  for _:!{bits[level]}..{bits[level]} {{")
        emit(level + 1, row + 2 ** (n - 1 - level))
        lines.append("  }")
        emit(level + 1, row)

    emit(0, 0)
    lines.append("}")
    return "\n".join(lines)


def _suptiftam_bit(i: int) -> str:
    """Variable name for input bit ``i`` (identifiers must be alphabetical)."""
    if i < 25:
        return chr(ord("b") + i)
    return "b" + _suptiftam_bit(i - 25)


def suptiftam(truth_table: str) -> str:
    """Build a Suptiftam program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Suptiftam has only ``+``/``-``/``/`` and no equality test, so the table
    is evaluated as a sum of minterms: each bit is read from its own input
    row and normalized to 0/1 with ``%-[read]22%`` (the literal ``22``
    parses in base 23 to 48), each minterm multiplies its bits (AND, via a
    recursive add-until-zero ``mulStep`` guarded by ``if``), and the sum is
    written to ``term``.  Exactly one minterm is 1 for any input, so the
    sum is the table entry.
    """
    n = _validate_truth_table(truth_table)
    names = [_suptiftam_bit(i) for i in range(n)]
    lines = [
        "sum=0",
        "p=1",
        "fd mulStep :x",
        "prod=%+[prod]a%",
        "x=%-[x]1%",
        "mulStep(:x:)if(x)",
        "fi",
    ]
    for name in names:
        lines.append(f"{name}=%-[read]22%")
        lines.append("down(:read:)")
    for row in range(2**n):
        if truth_table[row] != "1":
            continue
        lines.append("p=1")
        for i in range(n):
            bit = (row >> (n - 1 - i)) & 1
            factor = names[i] if bit else f"%-[1]{names[i]}%"
            lines += ["prod=0", f"a={factor}", "mulStep(:p:)if(p)", "p=prod"]
        lines.append("sum=%+[sum]p%")
    lines.append("term=sum")
    return "\n".join(lines)


def _flowchart_leaf(bit: str) -> list[str]:
    """Build a leaf column: force ``bit`` into the register, print, halt.

    The register holds whichever input bit the tree read last, so the leaf
    sets it outright (``[ }`` for one, ``{ ]`` for zero) rather than
    relying on what the routing happened to leave behind.
    """
    return [
        "[ }" if bit == "1" else "{ ]",
        " │ ",
        "\\ \\",
        " │ ",
        "(( ))",
    ]


def _flowchart_subtree(truth_table: str) -> list[str]:
    """Build the block for ``truth_table``, entered at its ``/ /`` node.

    Each level reads one input bit and switches on it.  The tree is always
    entered travelling downward, and a switch's sides are relative to the
    pointer's heading, so a set register turns the pointer east and a clear
    one turns it west: the table's zero half hangs to the west and its one
    half to the east, matching the index order.  Recursion bottoms out at
    :func:`_flowchart_leaf`.
    """
    if len(truth_table) == 1:
        return _flowchart_leaf(truth_table[0])

    half = len(truth_table) // 2
    west = _flowchart_subtree(truth_table[:half])
    east = _flowchart_subtree(truth_table[half:])

    west_width = max(len(row) for row in west)
    east_width = max(len(row) for row in east)
    west = [row.ljust(west_width) for row in west]
    east = [row.ljust(east_width) for row in east]

    gap = 3
    total = west_width + gap + east_width
    west_entry = west_width // 2
    east_entry = west_width + gap + east_width // 2
    middle = (west_entry + east_entry) // 2

    rail = [" "] * total
    for x in range(west_entry, middle):
        rail[x] = "─"
    for x in range(middle + 3, east_entry + 1):
        rail[x] = "─"
    rail[west_entry] = "┌"
    rail[east_entry] = "┐"
    switch = "".join(rail)
    switch = switch[:middle] + "< >" + switch[middle + 3 :]

    head = [
        " " * middle + "/ /",
        " " * (middle + 1) + "│",
        switch,
        " " * west_entry + "│" + " " * (east_entry - west_entry - 1) + "│",
    ]

    depth = max(len(west), len(east))
    west += [" " * west_width] * (depth - len(west))
    east += [" " * east_width] * (depth - len(east))
    body = [a + " " * gap + b for a, b in zip(west, east, strict=True)]

    return [row.ljust(total) for row in head + body]


def flowchart(truth_table: str) -> str:
    """Build a Flowchart program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The program is a binary decision tree drawn on the grid: every level
    reads one input bit with ``/ /`` and hands it to a ``< >`` switch whose
    two sides are the halves of the table, and each of the ``2**n`` leaves
    sets the register to its own digit, prints it, and halts.

    Unlike the repo's other 2D boolean generators there is no geometry to
    build for the branch itself -- Flowchart has a real conditional node --
    and each input arrives as a bare bit, so no per-input decoding loop is
    needed either.  What the layout has to get right instead is routing:
    every switch is centred over the two subtree entries it feeds, with
    rails drawn out to each.

    **The tree holds many ``/ /`` nodes but reads each input once.**  A
    depth-``n`` tree draws ``2**n - 1`` read nodes, one per internal node,
    yet any single run walks one root-to-leaf path and so executes exactly
    ``n`` of them -- the duplication is spatial, the way an unrolled
    brainfuck branch repeats ``,`` in each arm of a nested ``[ ]`` without
    any one execution reading twice.  This is deliberately *not* the
    once-only embedding rule that ``tools.boolean.parameterized`` documents:
    that rule exists so a language with no input mechanism cannot, through
    repeated ``{Xi}`` substitution, consult a bit more often than an
    input-capable language would.  Flowchart has a real input command, so
    it is an input-reading generator like :func:`streetcode` (whose ``I``
    commands likewise repeat across tree branches), not a parameterized one.

    An alternative construction reads all ``n`` bits up front into a deque
    and pops one per level instead, which exercises the deques -- the
    language's defining feature, untouched here.  It was built and verified
    over the same tables, and is worth revisiting if Flowchart ever gets a
    cross-check that would benefit from the wider coverage; it costs a
    ``4n``-row prologue and depends on push-top/pop-bottom being FIFO, a
    silent wrong-answer trap if the pop is ever changed to pop-top.
    """
    _validate_truth_table(truth_table)
    body = _flowchart_subtree(truth_table)
    width = max(len(row) for row in body)
    entry = body[0].index("/ /")
    head = [" " * entry + "( )", " " * (entry + 1) + "│"]
    return "\n".join(row.ljust(width) for row in head + body)
