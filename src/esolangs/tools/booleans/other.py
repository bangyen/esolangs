"""Boolean-function generators for languages in the ``other`` category."""

__all__ = [
    "between",
    "clockwise",
    "container",
    "laserfuck",
    "nevermind",
    "taglate",
    "three_x",
    "ztoalc_boolean",
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


def three_x(truth_table: str, n: int) -> str:
    """Build a 3x program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

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
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")

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


def _ztoalc_ok(lines: dict[int, str], n: int, inputs: str, expected: str) -> bool:
    """Fast ZTOALC simulator: True iff ``inputs`` prints ``expected`` once.

    Mirrors the interpreter's semantics exactly: the pointer follows the
    Collatz step (halving evens, ``3n+1`` odds) unless a ``jump`` fires,
    which advances the pointer by one.  A command line visited twice would
    re-execute (re-read, re-branch, or re-print), so any such revisit fails.
    """
    try:
        ptr = int(lines[0])
    except (KeyError, ValueError):
        return False
    var = [0] * n
    inp = list(inputs)
    out: list[str] = []
    visited: set[int] = set()
    steps = 0
    while ptr != 1:
        steps += 1
        if steps > 10**6:
            return False
        index = ptr - 1
        ins = lines.get(index, "")
        if ins:
            if index in visited:
                return False
            visited.add(index)
            if ins.startswith("print"):
                out.append(chr(int(ins.split()[1])))
                if len(out) > 1:
                    return False
            elif ins.startswith("jump"):
                if var[int(ins.split()[2][1])] != 0:
                    ptr += 1
                    continue
            elif "=" in ins:
                if not inp:
                    return False
                var[int(ins.split()[0][1])] = ord(inp.pop(0))
            elif "-" in ins:
                var[int(ins.split()[0][1])] -= int(ins.split()[2])
        ptr = ptr // 2 if ptr % 2 == 0 else 3 * ptr + 1
    return len(out) == 1 and out[0] == expected


def _ztoalc_lines(table: str, n: int, b1: int) -> dict[int, str]:
    """Place the reads, normalizes, branches, and leaves for ``table``."""
    start = b1 * 4**n
    lines: dict[int, str] = {0: str(start)}
    for i in range(n):
        lines[start // 2 ** (2 * i) - 1] = f"x{i} = input"
        lines[start // 2 ** (2 * i + 1) - 1] = f"x{i} - 48"

    def build(combos: list[int], root: int, depth: int) -> None:
        results = {table[c] for c in combos}
        if len(results) == 1:
            lines[root - 1] = f"print {48 + int(results.pop())}"
            return
        lines[root - 1] = f"jump a x{depth}"
        bit = n - 1 - depth
        zero = [c for c in combos if not (c >> bit) & 1]
        one = [c for c in combos if (c >> bit) & 1]
        build(zero, root // 2, depth + 1)
        build(one, 3 * root + 4, depth + 1)

    build(list(range(2**n)), b1, 0)
    return lines


def _ztoalc_symmetric(table: str, n: int) -> list[str] | None:
    """Build a branch-free linear program for a popcount-symmetric table.

    If ``table[c]`` depends only on ``popcount(c)``, the result is computable
    without a decision tree: sum the normalized input bits into ``s``, look
    the result up in a small ``n + 1``-entry table, and print it.  Every
    line sits on the pure power-of-two descent from ``2**L``, so the
    trajectory never revisits a line and no placement search is needed.
    The program is ``2**L`` lines (``L`` commands), so it is huge but
    collision-free; returns ``None`` for non-symmetric tables.
    """
    value: dict[int, str] = {}
    for combo in range(2**n):
        count = bin(combo).count("1")
        if count in value and value[count] != table[combo]:
            return None
        value[count] = table[combo]
    cmds: list[str] = []
    for i in range(n):
        cmds.append(f"x{i} = input")
        cmds.append(f"x{i} - 48")
    cmds.append("s = 0")
    for i in range(n):
        cmds.append(f"s += x{i}")
    cmds.append(f"t = [{n + 1}]")
    for count in range(n + 1):
        if value.get(count, "0") == "1":
            cmds.append(f"t[{count}] = 1")
    cmds.append("r = t[s]")
    cmds.append("r + 48")
    cmds.append("print r")
    size = 2 ** len(cmds)
    if size > 2**22:
        return None  # too large to materialize
    prog = [""] * size
    prog[0] = str(size)
    for j, cmd in enumerate(cmds):
        prog[2 ** (len(cmds) - j) - 1] = cmd
    return prog


def ztoalc_boolean(truth_table: str, n: int) -> str:
    """Build a ZTOALC program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    ZTOALC's control flow is the Collatz trajectory of line 1, so the
    generator lays out a decision tree on `p * 2**k` descents: branching at
    an even root lets a zero bit continue the descent (the Collatz step
    halves it) while a one bit jumps to `root + 1`, whose Collatz step lands
    on `4 * q` — so every branch gets a predictable, non-revisiting path.
    The reads and normalizations ride the initial `b1 * 4**n` descent.  A
    small ``b1`` is searched until the placement verifies against a fast
    simulator (each input must print exactly its table entry once, with no
    command line revisited).

    When the tree search finds no collision-free placement (dense tables
    like XOR4), a branch-free *linear* program is tried instead for
    popcount-symmetric tables: sum the bits and look the result up in a
    small table.  That program is guaranteed collision-free (a pure
    power-of-two descent) but huge (``2**L`` lines), so it is gated by a
    size limit and the generator raises :class:`ValueError` only for dense,
    non-symmetric tables past ``n == 3``.

    Verified exhaustively for every table at ``n <= 3`` and for structured
    and symmetric tables at ``n == 4``; all tests run the real interpreter.
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    for b1 in range(2 ** (n + 1), 4000, 4):
        lines = _ztoalc_lines(truth_table, n, b1)
        if all(
            _ztoalc_ok(
                lines,
                n,
                "".join(str((c >> (n - 1 - i)) & 1) for i in range(n)),
                truth_table[c],
            )
            for c in range(2**n)
        ):
            size = max(lines) + 1
            return "\n".join(lines.get(i, "") for i in range(size))
    linear = _ztoalc_symmetric(truth_table, n)
    if linear is not None:
        return "\n".join(linear)
    raise ValueError(
        "the ZTOALC boolean generator found no collision-free placement for "
        f"this table at n == {n}",
    )


def nevermind(truth_table: str, n: int) -> str:
    """Build a Nevermind program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Nevermind reads each input with ``input,?`` into its own variable, then a
    decision tree of nested ``if``/``endif`` blocks prints the result for the
    matching combination.
    """
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


def _validate_tt(truth_table: str, n: int) -> None:
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")


def between(truth_table: str, n: int) -> str:
    """Build a Between program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    The program reads each input bit as a line, converts it to an integer
    with ``c``, then walks a decision tree laid out linearly: every node
    tests bit ``i`` and, when the bit is zero, jumps over the ``1`` subtree
    to the ``0`` subtree; each leaf prints ``|0|``/``|1|`` and exits.  The
    branch addresses are 0-indexed line numbers, so the size of each subtree
    is computed ahead of the linear layout.
    """
    _validate_tt(truth_table, n)

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


def laserfuck(truth_table: str, n: int) -> str:
    r"""Build a LaserFuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    The laser starts at ``o`` with a random heading, so a mirror funnel
    (``|``/``^``/``_`` plus two ``}`` on the row above) sends every heading to
    the top row moving right.  There it reads ``n`` bits into cells 0..n-1
    (each ``,`` then 48 ``-`` normalizes ``'0'``/``'1'`` to 0/1) and enters a
    decision tree.  Each node at level ``i`` moves the pointer to cell ``i``,
    then lays down ``#`` ``v`` ``)`` ``\\``: the ``#`` skips the ``v`` on
    approach, ``)`` routes a zero cell through to ``\\`` (down column c+3) and
    a nonzero cell back to ``v`` (down column c+1); each child row's ``\\``
    turns the beam right into the child.  Leaves (one per input combination,
    at a dedicated high column so no ``+`` run crosses a descent column) move
    the pointer to cell ``n``, set it to 48+result, and hit ``x`` to halt.

    The first grid cell ``\\xff`` selects byte output mode: every touched
    cell with a nonnegative value prints as a byte.  The input cells hold 0/1
    (printed as NUL/SOH), so the verify harness's ``01`` filter leaves exactly
    the 48/49 result cell.  The tree is loop-free, so no loop-ring geometry is
    needed.
    """
    _validate_tt(truth_table, n)
    rows: int = 2 ** (n + 1) - 1
    total_cols: int = 3 + 49 * n + (2 ** (n + 1) - 1) * 6 + 2**n * 55 + 64
    grid = [[" "] * total_cols for _ in range(rows)]

    # the funnel: every heading ends up on row 0 moving right
    grid[0][0] = "\u00ff"
    grid[0][1] = "}"
    grid[0][2] = "}"
    grid[1][0] = "|"
    grid[1][1] = "o"
    grid[1][2] = "^"
    grid[2][1] = "_"

    # read n bits into cells 0..n-1 on row 0 (pointer ends at cell n-1)
    col = 3
    for i in range(n):
        grid[0][col] = ","
        col += 1
        for _ in range(48):
            grid[0][col] = "-"
            col += 1
        if i < n - 1:
            grid[0][col] = ">"
            col += 1

    # node rows: breadth-first, root at row 0 and children on lower rows
    def row(i: int, j: int) -> int:
        return int(2**i + j - 1)

    # internal-node columns (preorder); leaves get a dedicated high region
    cols: dict[tuple[int, int], int] = {}
    width = [col + 1 + n]  # room for the root's pointer-move cells

    def assign_col(i: int, j: int) -> int:
        if (i, j) in cols:
            return cols[(i, j)]
        c = width[0]
        cols[(i, j)] = c
        width[0] = c + 6
        if i < n - 1:
            assign_col(i + 1, 2 * j)
            assign_col(i + 1, 2 * j + 1)
        return c

    assign_col(0, 0)
    leaf_base = width[0] + 4  # past every internal column and descent column

    # leaves: one per input combination, at (level n, row, high column)
    for j in range(2**n):
        r = row(n, j)
        c = leaf_base + j * 55
        # the beam arrives from the parent's descent column; it first moved the
        # pointer to cell i (level i), so here it is at cell n-1
        grid[r][c] = ">"
        for k in range(48 + int(truth_table[j])):
            grid[r][c + 1 + k] = "+"
        grid[r][c + 1 + 48 + int(truth_table[j])] = "x"

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

    return "\n".join("".join(ln).rstrip() for ln in grid)


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


def taglate(truth_table: str, n: int) -> str:
    r"""Build a Taglate program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

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
    if n == 1:
        _validate_tt(truth_table, n)
        base = 48 + int(truth_table[0])
        coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
        seed = "0" + chr(coeff) + chr(base)
        return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"

    _validate_tt(truth_table, n)

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


def clockwise(truth_table: str, n: int) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.  The
    program prints the result bit seven times, as ``chr(127 * result)``.

    The program is a decision tree in a closed ring.  ``S`` zeroes the
    accumulator and seven ``.`` reads consume a ``0``/``1`` input char's seven
    bits, leaving its value bit in the accumulator.  At each node a ``?``
    turns the pointer by ``acc`` quarter-turns, so a zero bit continues down
    the spine while a one bit turns right (cw) into a column; three ``R`` in
    an L pattern turn it back down into the next column, at a ``2**(n-k)``
    displacement so each input combination reaches a unique leaf column.  A
    leaf prints ``S [,+] ;x7``, then a ``?`` (with acc reset to 1) turns it
    left onto a shared bottom row; an ``S`` after each exit keeps passing
    paths at acc=0 so they do not turn on another leaf's exit.  The row
    funnels left to the corner ``R`` and up column 0 to halt.
    """
    _validate_tt(truth_table, n)
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
        result = int(truth_table[combo])
        place((x, y), "S")
        place((x, y + 1), "+" if result else " ")
        for i in range(7):
            place((x, y + 2 + i), ";")
        # '?' turns by acc quarter-turns; acc must be exactly 1 to turn left
        # onto the bottom row, so add one increment only when the result is 0
        place((x, y + 9), "+" if not result else " ")
        place((x, y + 10), "?")

    build(0, root, 1, 0)

    bottom = 1 + 9 * n + 10
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


def container(truth_table: str, n: int) -> str:
    """Build a Container program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

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
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")

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
