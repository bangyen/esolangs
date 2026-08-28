"""Boolean-function generators for languages in the ``other`` category."""

# laserfuck, streetcode and ztoalc_l_boolean each own a file because their
# construction (a grid layout or a program search) dwarfs the rest of the
# category; they are re-exported here so this module stays the import site
# the package and tests already use.

from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _maybe_complement,
    _validate_truth_table,
    minterm_literals,
)
from esolangs.tools.boolean.laserfuck import laserfuck
from esolangs.tools.boolean.streetcode import streetcode
from esolangs.tools.boolean.ztoalc_l import ztoalc_l_boolean

__all__ = [
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
        # ``combo`` has the bits above level ``i`` set and the rest clear,
        # so it is the first row of the run this subtree covers.
        if i == n or len(set(truth_table[combo : combo + 2 ** (n - i)])) == 1:
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
        indent = "  " * k
        # ``row`` is accumulated a bit at a time, so at depth ``k`` it is a
        # partial index: shifting it into place names the first row of the
        # run its remaining bits span.
        lo = row << (n - k)
        if k == n or len(set(truth_table[lo : lo + 2 ** (n - k)])) == 1:
            lines.append(f"{indent}print,{truth_table[lo]}")
            return
        for bit in (0, 1):
            lines.append(f"{indent}if,${chr(ord('a') + k)},==,{bit}")
            build(k + 1, row * 2 + bit)
            lines.append(f"{indent}endif")

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

    A subtree whose rows all agree becomes a leaf rather than branching on
    bits that cannot change the answer.  Because the addresses come from
    ``size`` walking the tree a second time, the fold has to be a property
    of the path alone -- ``constant`` -- so both walks stop in the same
    places; a check either walk applied and the other did not would leave
    every branch below it naming the wrong line.
    """
    n = _validate_truth_table(truth_table)

    def first_row(path: list[int]) -> int:
        """Return the lowest table row ``path`` reaches.

        A full path spells a row outright; a short one has its unconsumed
        bits still to come, so it names the *start* of the ``2**(n - len)``
        run they span.  Shifting by those bits is what makes a folded leaf
        read its own slice rather than the small index the raw path spells.
        """
        row = 0
        for bit in path:
            row = row * 2 + bit
        return row << (n - len(path))

    def leaf_value(path: list[int]) -> int:
        return int(truth_table[first_row(path)])

    def constant(path: list[int]) -> bool:
        """Whether every row ``path`` reaches holds the same entry."""
        row = first_row(path)
        return len(set(truth_table[row : row + 2 ** (n - len(path))])) == 1

    def size(path: list[int]) -> int:
        if len(path) == n or constant(path):
            return 2
        return 1 + size([*path, 1]) + size([*path, 0])

    lines: list[str] = []
    for bit in range(n):
        lines.append(f"'{bit}'v.")
        lines.append(f"[{bit}]i.")
        lines.append(f"[{bit}]s|[{bit}]c.|")

    def emit(path: list[int], offset: int) -> int:
        # Must stop exactly where ``size`` stops: the branch addresses are
        # line numbers ``size`` computed ahead of the layout, so a subtree
        # that folds here and not there would name the wrong target.
        if len(path) == n or constant(path):
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
        base = _ASCII_ZERO + int(truth_table[0])
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

    The root node needs no spine of its own.  The pointer starts at ``(0, 0)``
    heading right and walks the whole top row into the corner ``R``, so seven
    ``.`` laid just left of that corner are the first instructions executed,
    and the accumulator is already zero when they run -- so the root's ``S``
    is a no-op too.  Hoisting those eight cells onto row 0 retires seven rows
    of grid, roughly a fifth of the blanks in a small table.  It needs seven
    free columns left of the root, i.e. ``2 ** (n + 1) >= 7``, so ``n == 1``
    (four columns) keeps the spine; widening that ring would cost more than
    the rows save.

    A subtree whose rows all agree stops branching, which narrows the ring:
    the width is the sum of the displacements its nodes spend, and a folded
    node spends none.  Since that width grows as ``2 ** (n + 1)``, the
    saving is real -- a constant table is 411 characters against 621 at
    ``n == 3`` and 863 against 1479 at ``n == 4``.

    Two things the fold does *not* get to do.  It cannot drop the reads:
    Clockwise reads inside the tree, seven ``.`` per level, so a folded
    column still spends them (and an ``S`` where the ``?`` would have been,
    keeping every column the same height so each leaf's exit lands on the
    shared bottom row the ring closes through).  And it cannot narrow past
    the hoist: at ``n == 2`` a tree folded to seven columns loses those
    seven hoisted rows and comes out *larger* than the unfolded program,
    263 characters against 255, so the width floors at what the hoist
    needs.
    """
    n = _validate_truth_table(truth_table)
    cells: dict[tuple[int, int], str] = {}

    def constant(bit: int, combo: int) -> bool:
        """Whether every row this subtree covers agrees.

        Rows split most-significant-first, so the subtree entered at
        ``bit`` with prefix ``combo`` covers the contiguous run of
        ``2 ** (n - bit)`` rows starting at ``combo << (n - bit)``.
        """
        span = 2 ** (n - bit)
        start = combo << (n - bit)
        return len(set(truth_table[start : start + span])) == 1

    # The spine starts far enough right that the tree's leftward branches
    # clear column 0, which holds the closing corner.  A node at ``bit``
    # displaces its one-branch ``2**(n - bit)`` to the left and puts two
    # ``R`` one column further, so the whole tree spans
    # ``sum(2**(n - bit)) + 1 == 2**(n + 1) - 1`` columns left of the spine
    # and ``2**(n + 1)`` leaves exactly one free column at the left edge.
    # Anything wider is dead space: the turns are relative, so the tree's
    # absolute column never matters.
    #
    # A folded node spends no displacement, since it has no one-branch to
    # send anywhere -- so the span is summed over the nodes that actually
    # branch rather than assumed full.  This is where the fold pays: the
    # full width grows as ``2 ** (n + 1)``, and a table whose subtrees
    # collapse needs only the columns its surviving branches displace.
    def tree_span(bit: int, combo: int) -> int:
        if bit == n or (bit > 0 and constant(bit, combo)):
            return 0
        below: int = max(
            tree_span(bit + 1, combo << 1),
            tree_span(bit + 1, (combo << 1) | 1),
        )
        displacement: int = 2 ** (n - bit)
        return displacement + below

    # Never narrow past the hoist's own requirement.  The hoist puts the
    # root's seven reads on row 0, left of the corner, which retires seven
    # rows of spine -- worth more than the columns narrowing below it would
    # save, and at ``n == 2`` a tree folded to seven columns loses the
    # hoist and comes out *larger* than the unfolded program (263 against
    # 255 characters).  So the tree may shrink only down to the width the
    # hoist needs, and a table whose fold would go further simply keeps
    # those columns blank.
    root = max(tree_span(0, 0) + 2, 8 if 2 ** (n + 1) >= 8 else 0)
    # Seven free columns left of the root are what the hoist needs; see
    # above.
    hoist = root >= 8
    shift = 7 if hoist else 0

    def place(node: tuple[int, int], ch: str) -> None:
        cells[node] = ch

    def build(bit: int, x: int, y: int, combo: int) -> None:
        if bit == n:
            leaf(x, y, combo)
            return
        if bit > 0 and constant(bit, combo):
            # Every row below here agrees, so the remaining bits cannot
            # change the answer and this column needs no more branching.
            # The reads are not optional, though: a program whose input
            # count depended on its table would desync a caller feeding
            # several from one stream, and unlike the tape generators
            # clockwise reads *inside* the tree.  So the skipped levels
            # still spend their ``S`` and seven ``.`` -- everything but
            # the ``?`` that would have turned the pointer.
            # A skipped level spends 9 rows in an unfolded column (``S``,
            # seven ``.``, ``?``) and only 8 here, since nothing turns.  The
            # ninth is padded with an ``S`` -- a no-op on an accumulator the
            # reads leave at 0 or 1, and the reads reset it anyway -- so the
            # column still ends on the shared bottom row.  Every leaf's exit
            # has to land there or the ring does not close.
            for level in range(n - bit):
                place((x, y + 9 * level), "S")
                for i in range(7):
                    place((x, y + 9 * level + 1 + i), ".")
                place((x, y + 9 * level + 8), "S")
            leaf(x, y + 9 * (n - bit), combo << (n - bit))
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
        for bit in format(_ASCII_ZERO + result, "07b"):
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

    # Hoisting the root's reads onto row 0 retires seven rows of spine, so the
    # tree starts that much higher and every row below rides up with it.
    build(0, root, 1 - shift, 0)

    # A folded column pads its skipped levels to the same 9 rows an
    # unfolded one spends, so every column is the same height however much
    # of it folded and the bottom row is where it always was.  The fold
    # buys columns, not rows: the width is what grows as ``2 ** (n + 1)``.
    bottom = 1 + 9 * n + _CLOCKWISE_LEAF - 1 - shift
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
    # The grid is a fixed-size rectangle of blanks that the cells are painted
    # into, so a row's trailing filler is never reached; the interpreter pads
    # short rows itself, so trimming it changes nothing but the file.
    return "\n".join("".join(row).rstrip() for row in grid)


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

    That last block costs one line per row the table sends to 1, so a dense
    table is summed from its **zero** rows instead: ``OUT`` starts at 49 and
    each surviving zero row subtracts one, printing ``49 - S``.  The clamp
    at zero never bites, since the value stays at 48 or 49.  Worth up to
    12.7% at ``n == 4`` (1356 characters down to 1184 for fifteen ones of
    sixteen); the per-row survivor blocks above are fixed and unaffected.
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
    # OUT is 48 plus one ``+1`` per row the table sends to 1, so a dense
    # table pays for nearly every row.  Evaluating the *zero* rows instead
    # costs one line each and starts from 49, subtracting: ``49 - S`` is the
    # complement, and since ``S`` is 0 or 1 the value stays at 48 or 49, so
    # the container's clamp at zero never bites.  Whichever row-set is
    # smaller wins; ties keep the plain form.
    ones = truth_table.count("1")
    invert = ones > 2**n - ones
    lines.append("OUT:")
    lines.append(f"+{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n}")
    lines.append(f"-{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n + 1}")
    wanted = "0" if invert else "1"
    delta = "-1" if invert else "+1"
    for row in range(2**n):
        if truth_table[row] == wanted:
            lines.append(f"{delta} S{row}>=Gout")
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

    def emit(level: int, row: int, depth: int) -> None:
        indent = "  " * depth
        if level == n or len(set(truth_table[row : row + 2 ** (n - level)])) == 1:
            byte = _ASCII_ZERO + int(truth_table[row])
            lines.append(f"{indent}out {','.join(format(byte, '08b'))};")
            lines.append(f"{indent}return 0;")
            return
        lines.append(f"{indent}for _:!{bits[level]}..{bits[level]} {{")
        emit(level + 1, row + 2 ** (n - 1 - level), depth + 1)
        lines.append(f"{indent}}}")
        emit(level + 1, row, depth)

    emit(0, 0, 1)
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

    A table with more ones than zeros is summed over its *zero* rows and the
    sum inverted, since a minterm is four lines per input and ``1 - sum`` is
    one line however many it saves.  No constant table needs excluding here,
    unlike the gate-network generators: an all-ones table complements to no
    minterms at all, leaving ``sum`` at 0, and ``1 - 0`` is the 1 it should
    print.
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
    # One minterm per row selected, so a dense table is summed over its
    # zeros and the sum inverted -- ``1 - sum`` is one line however many
    # minterms it saves.
    table, invert = _maybe_complement(truth_table)
    for row in range(2**n):
        if table[row] != "1":
            continue
        lines.append("p=1")
        for i, negated in minterm_literals(row, n):
            factor = f"%-[1]{names[i]}%" if negated else names[i]
            lines += ["prod=0", f"a={factor}", "mulStep(:p:)if(p)", "p=prod"]
        lines.append("sum=%+[sum]p%")
    lines.append("term=%-[1]sum%" if invert else "term=sum")
    return "\n".join(lines)


# A leaf is exactly as wide as the ``(( ))`` it ends on, so consecutive
# leaves abut and the tree needs no gutter between them at all.
_FLOWCHART_PITCH = 5


def _flowchart_cells(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves are placed first, on a fixed pitch, and the switches are then
    collapsed upwards: each pair of entry columns yields a ``< >`` centred
    between them with rails drawn out to both.  Positioning everything from
    the leaf pitch is what keeps the drawing tight -- an earlier recursive
    version assembled each subtree into its own padded block and separated
    the blocks by a gutter, which cost a column of blanks for every leaf at
    every level even though two ``(( ))`` boxes may sit flush against each
    other.

    Rows run ``( )``, its rail, then four rows per level (``/ /``, a rail,
    ``< >``, a rail), then the five-row leaf block.
    """
    cells: dict[tuple[int, int], str] = {}

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    n = (len(truth_table) - 1).bit_length()
    leaf_top = 2 + 4 * n

    def leaf(slot: int, bit: str) -> int:
        """Draw the leaf for ``bit`` in column slot ``slot``; return its middle.

        Leaf ``k`` spans columns ``5k`` to ``5k + 4``, so its middle -- the
        column every rail in that leaf's band lands on -- is ``5k + 2``.
        """
        middle = _FLOWCHART_PITCH * slot + 2
        put(middle - 1, leaf_top, "[ }" if bit == "1" else "{ ]")
        cells[(middle, leaf_top + 1)] = "│"
        put(middle - 1, leaf_top + 2, "\\ \\")
        cells[(middle, leaf_top + 3)] = "│"
        put(middle - 2, leaf_top + 4, "(( ))")
        return middle

    def switch(depth: int, west: int, east: int) -> int:
        """Join two subtrees at ``depth``; return the column it sits on."""
        switch_row = 4 + 4 * depth
        middle = (west + east) // 2
        put(middle - 1, switch_row - 2, "/ /")
        cells[(middle, switch_row - 1)] = "│"
        put(middle - 1, switch_row, "< >")
        for x in range(west + 1, middle - 1):
            cells[(x, switch_row)] = "─"
        for x in range(middle + 2, east):
            cells[(x, switch_row)] = "─"
        cells[(west, switch_row)] = "┌"
        cells[(east, switch_row)] = "┐"
        cells[(west, switch_row + 1)] = "│"
        cells[(east, switch_row + 1)] = "│"
        return middle

    # Slots are handed out left to right as the walk reaches each leaf, so a
    # folded subtree takes one column band instead of the ``2**k`` its rows
    # would have filled -- the drawing narrows rather than leaving a gap.
    slots = [0]

    def walk(lo: int, hi: int, depth: int) -> int:
        """Draw the subtree for ``truth_table[lo:hi]``; return its column.

        ``depth`` is the level it sits at, which fixes its rows; its columns
        come from the leaf slots it consumes.
        """
        if len(set(truth_table[lo:hi])) == 1:
            # Constant: no branch below here can change the answer, so this
            # is a leaf.  Leaves all sit on the bottom row whatever their
            # depth, so the rail from the switch above covers the levels
            # this fold skipped: the rows are a fixed grid and only the
            # branching goes away.
            middle = leaf(slots[0], truth_table[lo])
            slots[0] += 1
            for y in range(4 * depth + 2, leaf_top):
                cells.setdefault((middle, y), "│")
            return middle
        half = (hi - lo) // 2
        west = walk(lo, lo + half, depth + 1)
        east = walk(lo + half, hi, depth + 1)
        return switch(depth, west, east)

    root = walk(0, len(truth_table), 0)
    put(root - 1, 0, "( )")
    cells[(root, 1)] = "│"
    return cells


def _flowchart_render(cells: dict[tuple[int, int], str]) -> str:
    """Flatten a painted cell map into the finished program text."""
    height = max(y for _, y in cells) + 1
    width = max(x for x, _ in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    return "\n".join("".join(row).rstrip() for row in grid)


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

    The leaves are laid down first, on a pitch of exactly one ``(( ))``
    width, and the switches are collapsed upwards from them.  Nothing
    separates one leaf from the next: two ``(( ))`` boxes may sit flush
    against each other, since a rail only has to clear a node when it needs
    to pass *through* that node's row.  Sibling subtrees never do -- they
    descend in their own column bands -- so the gutter an earlier version
    kept between them was never load-bearing, and dropping it takes the
    ``n = 4`` drawing from 2444 characters to 1557.

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
    return _flowchart_render(_flowchart_cells(truth_table))
