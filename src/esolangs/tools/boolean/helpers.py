r"""Shared helpers for the boolean-function program generators."""

from collections.abc import Callable, Iterable
from itertools import permutations

from esolangs.exceptions import TruthTableError

# ``ord("0")``.
# result prints as.
# generator that reads or.
# of ``+`` or ``-`` reads as a.
_ASCII_ZERO = 48
_ASCII_ONE = _ASCII_ZERO + 1  # ``ord("1")``, the digit the.

# Largest input count.
# search builds ``n!`` programs.
# is the product of two.
# 64-row table (milliseconds),.
# would be 479 million.
_ORDER_SEARCH_MAX = 6


def _validate_truth_table(truth_table: str) -> int:
    r"""Validate a truth table and return its input count ``n``."""
    n = _validate_shape(truth_table)
    if n == 0:
        raise TruthTableError(
            "truth table needs at least one input (n >= 1); "
            "a one-entry table is a constant, not a boolean function"
        )
    return n


def _validate_shape(truth_table: str) -> int:
    r"""Validate a table's *shape* only, allowing a nullary one."""
    # The alphabet is checked first.
    # complaint: ``01a`` is three.
    # answered it with "must have a.
    # and never mentioned the ``a``.
    # .
    # Spelled as a set difference.
    # order search revalidates the.
    # runs ~720 times per call at.
    # 2**n shows up (0.86s of the.
    if set(truth_table) - {"0", "1"}:
        # The *argument*, plus which.
        # printed ``sorted(set(...))``,.
        # was told "got 'enos'" -- a.
        # reads like a shell-quoting.
        # validator in ``encode``.
        bad = next((i, c) for i, c in enumerate(truth_table) if c not in {"0", "1"})
        raise TruthTableError(
            f"truth table must contain only '0' and '1', got {truth_table!r} "
            f"-- {bad[1]!r} at position {bad[0]} is not one of them"
        )
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        # The likeliest first error.
        # them to do the arithmetic.
        # this is the cold path -- the.
        # at n=6, but only ever raises.
        between = (
            f"; {len(truth_table)} is between {2**n} "
            f"({n} input{'' if n == 1 else 's'}) and "
            f"{2 ** (n + 1)} ({n + 1} input{'' if n + 1 == 1 else 's'})"
            if truth_table
            else ""
        )
        raise TruthTableError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}{between}",
        )
    return n


def _complement(truth_table: str) -> str:
    r"""Return the bitwise complement of ``truth_table``."""
    return "".join("1" if c == "0" else "0" for c in truth_table)


def _maybe_complement(truth_table: str) -> tuple[str, bool]:
    r"""Return the table (or its complement) and whether it was flipped."""
    if truth_table.count("1") > len(truth_table) // 2:
        return _complement(truth_table), True
    return truth_table, False


def minterm_literals(row: int, n: int) -> list[tuple[int, bool]]:
    r"""Return the literals whose product is 1 exactly on ``row``."""
    return [(i, not (row >> (n - 1 - i)) & 1) for i in range(n)]


SetBit = Callable[[int, int], str]


def instantiate(template: str, bits: list[int], set_bit: SetBit) -> str:
    r"""Substitute each ``{Xi}`` placeholder."""
    for i, bit in enumerate(bits):
        template = template.replace("{X" + str(i) + "}", set_bit(i, bit))
    return template


def permute_truth_table(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Rewrite ``truth_table`` so level ``k`` splits on original input."""
    _validate_truth_table(truth_table)
    return read_at(truth_table, perm, len(perm))


def essential_inputs(truth_table: str, n: int) -> list[int]:
    r"""Which input positions the table's value actually depends on."""
    return [
        i
        for i in range(n)
        if any(
            truth_table[row] != truth_table[row ^ (1 << (n - 1 - i))]
            for row in range(2**n)
        )
    ]


def read_at(truth_table: str, inputs: tuple[int, ...] | list[int], n: int) -> str:
    r"""Return the ``len(inputs)``-input table read at the given input."""
    # The row indices are built by.
    # each row's bits: slot ``k``.
    # appending ``o | mask`` after.
    # That is O(2**k) list work.
    # doubling because the order.
    originals = [0]
    for i in inputs:
        mask = 1 << (n - 1 - i)
        originals = [x for o in originals for x in (o, o | mask)]
    return "".join([truth_table[o] for o in originals])


def stored_inputs(truth_table: str, perm: tuple[int, ...]) -> set[int]:
    r"""Return the *stream* inputs a decision tree over ``perm`` has to."""
    n = _validate_truth_table(truth_table)
    branching = {
        k
        for k in range(n)
        if any(
            truth_table[r] != truth_table[r | (1 << (n - 1 - k))]
            for r in range(2**n)
            if not r & (1 << (n - 1 - k))
        )
    }
    return {perm[k] for k in branching}


def minterm_sum[Factor](
    truth_table: str,
    literal: Callable[[int, bool], Factor],
    product: Callable[[list[Factor]], Factor],
    accumulate: Callable[[Factor], None],
) -> tuple[list[int], int, bool]:
    r"""Fold each 1-row's literal product into a running sum."""
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    reduced = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)
    table, inverted = _maybe_complement(reduced)
    for row in range(2**width):
        if table[row] == "0":
            continue
        factors = [
            literal(used[slot], negated)
            for slot, negated in minterm_literals(row, width)
        ]
        accumulate(product(factors))
    return used, width, inverted


def best_input_order(
    truth_table: str,
    build: Callable[[str, tuple[int, ...]], str],
) -> str:
    r"""Return the shortest program over every input order."""
    n = _validate_truth_table(truth_table)
    identity = tuple(range(n))
    if n <= _ORDER_SEARCH_MAX:
        orders = [p for p in permutations(range(n)) if p != identity]
    else:
        greedy = _greedy_input_order(truth_table, n)
        orders = [] if greedy == identity else [greedy]

    # An empty candidate means.
    # stack reader reaches only.
    # it cannot stack comes back.
    # winning on length 0.
    # and gets the plain behaviour.
    # this: it searched for a.
    # had none.
    # reorder at all, so it is no.
    best = build(truth_table, identity)
    for perm in orders:
        candidate = build(permute_truth_table(truth_table, perm), perm)
        if candidate and (not best or len(candidate) < len(best)):
            best = candidate
    return best


def _greedy_input_order(truth_table: str, n: int) -> tuple[int, ...]:
    r"""Pick an input order one level at a time, for tables too wide to."""
    order: list[int] = []
    remaining = list(range(n))
    # Blocks of rows still to be.
    # that agree on every input.
    blocks = [list(range(2**n))]
    # The loop always leaves by the.
    # separates every row, so.
    # latest, and ``remaining`` is.
    while remaining:  # pragma: no branch - always exits via the break
        best_input = remaining[0]
        best_score = -1
        for i in remaining:
            bit = 1 << (n - 1 - i)
            score = 0
            for block in blocks:
                for half in (
                    [r for r in block if not r & bit],
                    [r for r in block if r & bit],
                ):
                    if half and len({truth_table[r] for r in half}) == 1:
                        score += 1
            if score > best_score:
                best_input, best_score = i, score
        order.append(best_input)
        remaining.remove(best_input)
        bit = 1 << (n - 1 - best_input)
        split = []
        for block in blocks:
            for half in (
                [r for r in block if not r & bit],
                [r for r in block if r & bit],
            ):
                # A block that is already.
                if half and len({truth_table[r] for r in half}) > 1:
                    split.append(half)
        blocks = split
        if not blocks:
            # Everything below folds; the.
            # keep it ascending to stay.
            order.extend(remaining)
            break
    return tuple(order)


# The walker only concatenates.
# inside one, so a token is.
# for most generators, an.
type Leaf[Token] = Callable[[int, int], list[Token]]
type Node[Token] = Callable[[int, list[Token], list[Token], int], list[Token]]


def decision_tree_tokens[Token](
    truth_table: str,
    leaf: Leaf[Token],
    node: Node[Token],
    *,
    parent_width: int | Callable[[int], int] = 0,
    start: int = 0,
    collapse: bool = False,
) -> list[Token]:
    r"""Walk a truth table's decision tree, combining caller-emitted parts."""
    n = _validate_truth_table(truth_table)
    width = parent_width if callable(parent_width) else lambda _level: parent_width

    def walk(level: int, lo: int, hi: int, at: int) -> list[Token]:
        # ``count`` over the span.
        # the constant test runs at.
        # candidates, and it is also.
        # off, which the set built.
        if level == n or (
            collapse and truth_table.count(truth_table[lo], lo, hi) == hi - lo
        ):
            return leaf(level, lo)
        half = (hi - lo) // 2
        below = at + width(level)
        zero = walk(level + 1, lo, lo + half, below)
        one = walk(level + 1, lo + half, hi, below + len(zero))
        return node(level, zero, one, at)

    return walk(0, 0, len(truth_table), start)


def decision_tree_program(truth_table: str, right: str, left: str) -> str:
    r"""Build a brainfuck-family decision-tree program for ``truth_table``."""
    return best_input_order(
        truth_table,
        lambda table, perm: _decision_tree_program(table, right, left, perm),
    )


def _decision_tree_program(
    truth_table: str,
    right: str,
    left: str,
    perm: tuple[int, ...],
) -> str:
    r"""Emit one input order's program; see :func:`decision_tree_program`."""
    n = _validate_truth_table(truth_table)

    cells: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        delta = target - pos
        cells.append(right * delta if delta >= 0 else left * -delta)
        pos = target

    # read bits b_i at cell 2i,.
    for i in range(n):
        cells.append(",")
        # ``append`` of the run, not.
        # is 48 long and the join sees.
        # order search pays the.
        cells.append("-" * _ASCII_ZERO)
        if i < n - 1:
            move(pos + 2)

    # decision tree: node i entered.
    result = 2 * n

    def constant(i: int, combo: int) -> str | None:
        r"""Return the shared value of the subtree at ``(i, combo)``, else None."""
        span = 2 ** (n - i)
        rows = truth_table[combo : combo + span]
        return rows[0] if len(set(rows)) == 1 else None

    def branch(i: int, combo: int) -> None:
        r"""Emit one side of node ``i``: a leaf when constant, else a subtree."""
        value = constant(i + 1, combo)
        if value is None:
            # A subtree is entered at the.
            # ``2 * perm[i + 1]`` --.
            # identity, so the target is.
            move(2 * perm[i + 1])
            node(i + 1, combo)
        elif value == "1":
            move(result)
            cells.append("+")

    def node(i: int, combo: int) -> None:
        r"""Emit node ``i``: test ``b_i``, run one side, and leave both cells."""
        bit = 2 * perm[i]
        flag = bit + 1
        one = combo | (1 << (n - 1 - i))
        move(flag)
        cells.append("+")  # flag = 1, pending.
        move(bit)
        cells.append("[-")  # one-side: if b_i, and clear.
        move(flag)
        cells.append("-")  # the one-side ran, so the.
        branch(i, one)
        move(bit)
        cells.append("]")
        move(flag)
        cells.append("[-")  # zero-side: the flag survived,.
        branch(i, combo)
        move(flag)
        cells.append("]")

    move(2 * perm[0])
    node(0, 0)

    # One print, below the tree.
    # the result cell, so the ASCII.
    # every leaf -- which is what.
    # characters on.
    move(result)
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    return "".join(cells)


# The build plan for every.
# ``(needed, decompositions)``.
# constants (beyond k1/k2).
# maps each such constant to.
_PLAN: dict[int, tuple[frozenset[int], dict[int, tuple[int, int, int]]]] = {
    1: (frozenset(), {}),
    2: (frozenset(), {}),
}


def _extend_plans(maxval: int) -> None:
    r"""Fill ``_PLAN`` up to ``maxval`` with minimal two-line build plans."""
    for m in range(3, maxval + 1):
        if m in _PLAN:
            continue
        best: tuple[frozenset[int], dict[int, tuple[int, int, int]]] | None = None
        for b in range(1, m, 2):
            for a in range(1, min(m // b + 1, m)):
                rem = m - b * a
                need = frozenset({m}) | _PLAN[b][0] | _PLAN[a][0]
                if rem > 2:
                    need |= _PLAN[rem][0]
                if best is None or len(need) < len(best[0]):
                    best = (need, {m: (b, a, rem)})
        if best is None:
            raise AssertionError("b = 1 always yields a finite plan")
        plan = dict(best[1])
        for v in best[0]:
            if v >= 3 and v != m:
                plan.update(_PLAN[v][1])
        _PLAN[m] = (best[0], plan)


def _cm_constants(needed: Iterable[int]) -> list[str]:
    r"""Lines building Collatz Multiverse constants for the values in."""
    need = sorted(n for n in set(needed) if n > 2)
    lines = [
        "k1 = negativeOne x + negativeOne, NOT PRINT.",
        "k1 = negativeOne x + zero, NOT PRINT.",
        "k2 = negativeOne x + negativeOne, NOT PRINT.",
        "k2 = negativeOne x + k1, NOT PRINT.",
    ]
    if not need:
        return lines
    _extend_plans(max(need))
    total: frozenset[int] = frozenset()
    decomp: dict[int, tuple[int, int, int]] = {}
    for n in need:
        s, d = _PLAN[n]
        total |= s
        decomp.update(d)
    for n in range(3, max(need) + 1):
        if n in total:
            b, a, c = decomp[n]
            lines.append(f"k{n} = negativeOne x + k{b}, NOT PRINT.")
            if c == 0:
                lines.append(f"k{n} = k{a} x + zero, NOT PRINT.")
            else:
                lines.append(f"k{n} = k{a} x + k{c}, NOT PRINT.")
    return lines
