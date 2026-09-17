"""Shared helpers for the boolean-function program generators.

A valid table has ``2**n`` entries, so ``n`` is recovered from the length
and the generators take no ``n`` parameter.
"""

from collections.abc import Callable, Iterable, Sequence

from esolangs.exceptions import TruthTableError

# ``ord("0")``.  Input digits arrive as 48/49 from a byte-oriented read, and a
# result prints as ``_ASCII_ZERO + bit``, so this offset appears in every
# generator that reads or writes a digit.  Named because a bare ``48`` in a run
# of ``+`` or ``-`` reads as a magic number.
_ASCII_ZERO = 48
_ASCII_ONE = _ASCII_ZERO + 1  # ``ord("1")``, the digit the other branch prints


def constant_span_test(truth_table: str) -> Callable[[int, int], bool]:
    """Return an O(1) test for whether a half-open table span is constant."""
    ones = [0]
    for bit in truth_table:
        ones.append(ones[-1] + (bit == "1"))

    def constant(start: int, stop: int) -> bool:
        count = ones[stop] - ones[start]
        return count in (0, stop - start)

    return constant


def _validate_truth_table(truth_table: str) -> int:
    """Validate a truth table and return its input count ``n``.

    A one-entry table (``2**0``) is refused: it is a constant, not a
    function of any input, and 44 generators used to build one, 24 then
    crashing with ``IndexError`` and 16 with ``negative shift count``.
    """
    n = _validate_shape(truth_table)
    if n == 0:
        raise TruthTableError(
            "truth table needs at least one input (n >= 1); "
            "a one-entry table is a constant, not a boolean function"
        )
    return n


def _validate_shape(truth_table: str) -> int:
    """Validate a table's *shape* only, allowing a nullary one.

    Minifuck's ``_solve`` reduces to essential inputs and can reach a
    one-entry table on the way down; its public entry still validates in full.
    """
    # Alphabet first: length-first answered ``01a`` with "got 3 entries"
    # and never named the ``a``.  A set difference, since this runs per
    # character on every candidate build.
    if set(truth_table) - {"0", "1"}:
        # The *argument*, plus which character is wrong and where.  This
        # printed ``sorted(set(...))``, so someone who typed ``nonsense``
        # was told "got 'enos'" -- a string they had never seen, which
        # reads like a shell-quoting bug rather than a typo.  The sibling
        # validator in ``encode`` echoed the argument all along.
        bad = next((i, c) for i, c in enumerate(truth_table) if c not in {"0", "1"})
        raise TruthTableError(
            f"truth table must contain only '0' and '1', got {truth_table!r} "
            f"-- {bad[1]!r} at position {bad[0]} is not one of them"
        )
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        # The likeliest first error anyone gets, and the rule alone leaves
        # them to do the arithmetic.  The brackets are cheap here because
        # this is the cold path and only ever raises once.
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
    """Return the bitwise complement of ``truth_table``."""
    return "".join("1" if c == "0" else "0" for c in truth_table)


def _maybe_complement(truth_table: str) -> tuple[str, bool]:
    """Return the table (or its complement) and whether it was flipped.

    A sum of minterms costs one term per selected row, so more ones than
    zeros is cheaper complemented and inverted once.  Every caller reads
    the *returned* table; how the flag is spent is per-language, often free
    (Collatz Multiverse's OR, Point Break's ``1 - f`` guard).  A constant
    table is the caller's to exclude: all-ones complements to no minterms,
    the all-zeros shape, which is wrong where the empty case is special
    (Circuit Diagram's self-fed gate).
    """
    if truth_table.count("1") > len(truth_table) // 2:
        return _complement(truth_table), True
    return truth_table, False


def minterm_literals(row: int, n: int) -> list[tuple[int, bool]]:
    """Return the literals whose product is 1 exactly on ``row``.

    One ``(input, negated)`` pair per input in input order; MSB-first
    indexing makes input ``i`` bit ``n - 1 - i``.  Every sum-of-minterms
    generator re-derived ``(k >> (n - 1 - i)) & 1``; what it does with a
    literal stays per-language.  Which rows to enumerate is the caller's
    (:func:`grapheme` takes the shorter of the one- and zero-rows).
    """
    return [(i, not (row >> (n - 1 - i)) & 1) for i in range(n)]


#: One ``(zero, one)`` pair per input, in name order: what a template's
#: runs are filled with.  Each pair is equal width, checked by
#: :func:`check_setters`, so the constant-width convention is a property
#: of the object rather than of every caller.
Setters = tuple[tuple[str, str], ...]


def check_setters(setters: Sequence[tuple[str, str]]) -> Setters:
    """Return ``setters`` as a tuple, refusing a pair of unequal width."""
    checked = tuple((zero, one) for zero, one in setters)
    for i, (zero, one) in enumerate(checked):
        if len(zero) != len(one):
            raise ValueError(
                f"input {i}'s setters differ in width ({len(zero)} against "
                f"{len(one)}), so the program's length would carry the bit"
            )
    return checked


#: The character a public template spells its inputs with, unless a
#: language declares another: outside every embedding language's alphabet.
TEMPLATE_CHAR = "$"


#: The first of the private-use characters a template is spelled with
#: while it is wrapped: input ``i`` is a run of ``chr(MARK + i)``, so a
#: wrapper sees every input as its own unbreakable token, even beside the
#: next, and the marks become the language's character afterwards.
MARK = 0xE000

#: The most inputs a template can carry marks for.
MOST_INPUTS = 64


def mark(i: int) -> str:
    """Return the character input ``i`` is spelled with while wrapping."""
    return chr(MARK + i)


def render(template: str, char: str | None, setters: Setters) -> str:
    """Return the template as a wrapper is handed it.

    Runs of :data:`TEMPLATE_CHAR` are each as long as their input's setters,
    so no separator is needed.  With ``char`` None each run is re-spelled
    as its own :func:`mark`, the form a wrapper keeps whole.
    """
    if char is not None:
        return template
    out, position = [], 0
    for i, (start, end) in enumerate(runs(template, TEMPLATE_CHAR, setters)):
        out.append(template[position:start] + mark(i) * (end - start))
        position = end
    return "".join(out) + template[position:]


def unmark(text: str, char: str, inputs: int) -> str:
    """Return ``text`` with every input's mark replaced by ``char``."""
    return text.translate({MARK + i: char for i in range(inputs)})


def runs(text: str, char: str, setters: Setters) -> list[tuple[int, int]]:
    """Return the ``[start, end)`` of each input's run in ``text``.

    Runs are consumed left to right in setter widths, and every ``char``
    must belong to one; a width-zero setter (%^2^-1's ignored input) has
    an empty run where the previous ended.
    """
    widths = [len(zero) for zero, _one in setters]
    spans: list[tuple[int, int]] = []
    position = 0
    for i, width in enumerate(widths):
        if width == 0:
            spans.append((position, position))
            continue
        start = text.find(char, position)
        if start < 0:
            raise ValueError(
                f"template has {i} run(s) of {char!r}, setters name {len(widths)}"
            )
        end = start + width
        if text[start:end] != char * width:
            raise ValueError(
                f"input {i}'s run of {char!r} at {start} is shorter than its "
                f"setter width {width}"
            )
        spans.append((start, end))
        position = end
    stray = text.find(char, position)
    if stray >= 0:
        raise ValueError(
            f"{char!r} at {stray} belongs to no input: {len(widths)} setter(s), "
            f"more runs than that"
        )
    return spans


def fill_runs(text: str, char: str, setters: Setters, bits: Sequence[int]) -> str:
    """Return ``text`` with each input's run replaced by its bit's setter."""
    if len(bits) != len(setters):
        raise ValueError(f"expected {len(setters)} bits, got {len(bits)}")
    out: list[str] = []
    position = 0
    for (start, end), (zero, one), bit in zip(
        runs(text, char, setters), setters, bits, strict=True
    ):
        out.append(text[position:start])
        out.append(one if bit else zero)
        position = end
    out.append(text[position:])
    return "".join(out)


def permute_truth_table(truth_table: str, perm: tuple[int, ...]) -> str:
    """Rewrite ``truth_table`` so level ``k`` splits on original input ``perm[k]``.

    The same function with its inputs renamed.  A subtree folds only when
    its rows agree, and the split order decides which rows a subtree
    covers: ``11110000`` folds after one split, ``10101010`` only at the
    bottom, and reordering lets the second be emitted as the first.
    """
    _validate_truth_table(truth_table)
    return read_at(truth_table, perm, len(perm))


def essential_inputs(truth_table: str, n: int) -> list[int]:
    """Which input positions the table's value actually depends on.

    Input ``i`` matters when flipping it changes some row; a table
    ignoring some inputs is a smaller table wearing extra ones, which
    :func:`read_at` projects down.  Three generators derived this
    independently before it moved here (checked equal to ``n == 4``).
    """
    return [
        i
        for i in range(n)
        if any(
            truth_table[row] != truth_table[row ^ (1 << (n - 1 - i))]
            for row in range(2**n)
        )
    ]


def read_at(truth_table: str, inputs: tuple[int, ...] | list[int], n: int) -> str:
    """Return the ``len(inputs)``-input table read at the given input positions.

    Slot ``k`` varies with original input ``inputs[k]``; every input not
    named is held at 0.  :func:`permute_truth_table` passes all ``n`` (a
    renaming); :func:`~esolangs.tools.minifuck._project` passes the
    essential inputs (holding an ignored one at 0 cannot change the answer).
    ``n`` is passed because the projected result is narrower than its input.
    """
    # The row indices are built by doubling rather than by re-scattering
    # each row's bits: slot ``k`` is the next-most-significant bit, so
    # appending ``o | mask`` after ``o`` extends the list in row order.
    # That is O(2**k) list work against O(2**k * k) bit tests -- worth the
    # doubling because order selection calls this once per candidate.
    originals = [0]
    for i in inputs:
        mask = 1 << (n - 1 - i)
        originals = [x for o in originals for x in (o, o | mask)]
    return "".join([truth_table[o] for o in originals])


def stored_inputs(truth_table: str, perm: tuple[int, ...]) -> set[int]:
    """Return the *stream* inputs a decision tree over ``perm`` has to keep.

    A level whose halves agree is never tested, so its read is discarded.
    The fold is computed in *level* space over the permuted table, the
    reads run in *stream* order, so the answer is translated back through
    ``perm``; mixing the frames stores the wrong bits.
    """
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
    """Fold each 1-row's literal product into a running sum.

    Returns ``(used, width, inverted)``; the seed and final flip are
    per-language.  Reduces to essential inputs, complements when cheaper,
    skips 0-rows, and per survivor folds ``literal(input, negated)``
    factors (named by original index) into a product then the sum.
    Callbacks run in the hand-written loops' order -- every literal, the
    product, the accumulate -- so a ``literal`` that allocates (Collatz
    Multiverse) does not drift.  Not for ROTfuck (three passes over all
    rows), Grapheme (builds both sides) or Circuit Diagram (routes a bus
    pair per literal).
    """
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


_GREEDY_ORDER_MAX_ARITY = 10


def best_input_order(
    truth_table: str,
    build: Callable[[str, tuple[int, ...]], str],
) -> str:
    """Return the shorter program from the identity and greedy input orders.

    ``build(permuted_table, perm)`` splits on ``perm[k]`` at level ``k``
    over the *permuted* table.  Through :data:`_GREEDY_ORDER_MAX_ARITY` the
    greedy order is scored level by level (``O(n**2 * 2**n)``), both built
    since routing costs can outweigh folds; wider tables use the identity.
    Identity first, ties keep it, so reordering only ever shrinks.
    Only the *test* order moves; the reads stay in input order.  That rules
    out Polynomial (one register, no storage: a bit is branched on before
    the next read).  6-5, Jaune and Bitdeque were wrongly excluded once
    (all have storage; Bitdeque's ``INJECT``/``EJECT`` make it a deque);
    6-5 keeps its node-read build as a candidate since hoisting has a
    price.  Modulous is a true negative: ``[PSH VAR1]`` stores, only
    ``[PRT VAR1 INT]`` reads a variable, and every conditional and
    ``ADD``/``SUB``/``JMP IF`` rejects a variable operand -- no return leg
    (verified against the interpreter and the wiki).
    """
    n = _validate_truth_table(truth_table)
    identity = tuple(range(n))
    greedy = (
        _greedy_input_order(truth_table, n)
        if n <= _GREEDY_ORDER_MAX_ARITY
        else identity
    )
    orders = [] if greedy == identity else [greedy]

    # An empty candidate means "this order could not be built" and is skipped
    # rather than winning on length 0.  Builders that always succeed retain
    # the plain behavior.
    best = build(truth_table, identity)
    for perm in orders:
        candidate = build(permute_truth_table(truth_table, perm), perm)
        if candidate and (not best or len(candidate) < len(best)):
            best = candidate
    return best


def _greedy_input_order(truth_table: str, n: int) -> tuple[int, ...]:
    """Pick an input order one level at a time.

    Score each unchosen input by the constant subtrees it creates among
    the live blocks; ties keep the lowest index so an unhelped table
    yields the identity.
    """
    order: list[int] = []
    remaining = list(range(n))
    # Blocks of rows still to be separated: each is a list of row indices
    # that agree on every input chosen so far.
    blocks = [list(range(2**n))]
    # The loop always leaves by the ``break`` below: picking every input
    # separates every row, so ``blocks`` is empty on the last pass at the
    # latest, and ``remaining`` is never the condition that ends it.
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
                # A block that is already constant needs no further splitting.
                if half and len({truth_table[r] for r in half}) > 1:
                    split.append(half)
        blocks = split
        if not blocks:
            # Everything below folds; the rest of the order cannot matter, so
            # keep it ascending to stay closest to the identity.
            order.extend(remaining)
            break
    return tuple(order)


# The walker only concatenates tokens and measures runs of them, never looks
# inside one, so a token is whatever the caller finds convenient: a string
# for most generators, an instruction tuple for S*bleq.
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
    """Walk a truth table's decision tree, combining caller-emitted parts.

    ``leaf(level, row)`` returns a leaf's tokens; ``node(level, zero, one,
    at)`` combines two finished subtrees, post-order.  ``collapse`` returns
    a leaf as soon as a subtree's rows agree.  ``at`` is the absolute index
    the subtree begins at, from ``start`` and ``parent_width`` (a constant
    or a function of level, as RAM0's address run), which is what lets
    Bitdeque, RAM0 and S*bleq name a jump target up front instead of
    backpatching.

    Deliberately cannot: act between the children (6-5, Jaune, Interprogck8
    allocate a label there; Polynomial threads a cell value); thread
    anything *down* (CV(N)(C)'s accumulator, Jaune's held bit, Circlefuck's
    pointer); lay the one subtree first (Between, CV(N)(C), Unsquare,
    Interprogck8); split other than MSB-first (Modulous, Unsquare); build a
    positional heap (Eval, Forth pin children at ``2i+1``/``2i+2``); skip a
    child (AddSubJump, Jaune descend into one half -- 24 of 256 tables came
    out longer at ``n == 3``); Lamfunc's plain string; the grid generators'
    plane.  Contrast :func:`decision_tree_program`, which shares a whole
    construction between two dialects.
    """
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)
    width = parent_width if callable(parent_width) else lambda _level: parent_width

    def walk(level: int, lo: int, hi: int, at: int) -> list[Token]:
        if level == n or (collapse and constant(lo, hi)):
            return leaf(level, lo)
        half = (hi - lo) // 2
        below = at + width(level)
        zero = walk(level + 1, lo, lo + half, below)
        one = walk(level + 1, lo + half, hi, below + len(zero))
        return node(level, zero, one, at)

    return walk(0, 0, len(truth_table), start)


def decision_tree_program(truth_table: str, right: str, left: str) -> str:
    """Build a brainfuck-family decision-tree program for ``truth_table``.

    Shared by Brainfuck and Dimensional, differing only in the move tokens
    (``>``/``<`` vs ``>0``/``<0``).  Each input is normalized into cell
    ``2i`` with its flag at ``2i + 1``: a node sets the flag, tests ``[b]``
    and clears the flag inside, then tests ``[flag]`` for the zero side,
    so exactly one side fires and both cells are left zero.  O(2**n).
    The flag replaced a precomputed ``1 - b`` per input (O(n**2): n == 10
    sparse went 2,646 -> 754 chars).  A leaf only records its bit (``+`` or
    nothing) and one ``.`` sits below the tree; with the fold, n == 10 xor
    went 77,939 -> 18,495.  A constant subtree collapses to a leaf; the
    reads are unconditional above the tree, so a folded program consumes
    its input the same way.  Factor most wants this: it refuses tables
    whose integer encoding exceeds Python's digit limit.
    """
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
    """Emit one input order's program; see :func:`decision_tree_program`.

    ``truth_table`` is already permuted; ``perm`` is spent only in the cell
    a node tests, ``2 * perm[i]``.  The reads above the tree are untouched.
    """
    n = _validate_truth_table(truth_table)

    cells: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        delta = target - pos
        cells.append(right * delta if delta >= 0 else left * -delta)
        pos = target

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero
    for i in range(n):
        cells.append(",")
        # ``append`` of the run, not ``extend`` over its characters: the run
        # is 48 long and the join sees the same text either way.
        cells.append("-" * _ASCII_ZERO)
        if i < n - 1:
            move(pos + 2)

    # decision tree: node i entered at cell 2i, exits at cell 2i+1
    result = 2 * n

    def constant(i: int, combo: int) -> str | None:
        """Return the shared value of the subtree at ``(i, combo)``, else None.

        The subtree's ``2**(n - i)`` rows are contiguous (MSB-first split).
        """
        span = 2 ** (n - i)
        rows = truth_table[combo : combo + span]
        return rows[0] if len(set(rows)) == 1 else None

    def branch(i: int, combo: int) -> None:
        """Emit one side of node ``i``: a leaf when constant, else a subtree.

        A ``'1'`` leaf is one ``+``; a ``'0'`` leaf is nothing, since the
        result cell is already zero.  Either way pointer-neutral.
        """
        value = constant(i + 1, combo)
        if value is None:
            # A subtree is entered at the cell holding *its* input, which is
            # ``2 * perm[i + 1]`` -- adjacent only when the order is the
            # identity, so the target is computed rather than stepped over.
            move(2 * perm[i + 1])
            node(i + 1, combo)
        elif value == "1":
            move(result)
            cells.append("+")

    def node(i: int, combo: int) -> None:
        """Emit node ``i``: test ``b_i``, run one side, and leave both cells zero.

        Entered at ``bit`` with the flag zero, left at the flag with both
        zero, so nodes nest.
        """
        bit = 2 * perm[i]
        flag = bit + 1
        one = combo | (1 << (n - 1 - i))
        move(flag)
        cells.append("+")  # flag = 1, pending
        move(bit)
        cells.append("[-")  # one-side: if b_i, and clear it so this ] exits
        move(flag)
        cells.append("-")  # the one-side ran, so the zero-side must not
        branch(i, one)
        move(bit)
        cells.append("]")
        move(flag)
        cells.append("[-")  # zero-side: the flag survived, so b_i was 0
        branch(i, combo)
        move(flag)
        cells.append("]")

    move(2 * perm[0])
    node(0, 0)

    # One print, below the tree.  Exactly one leaf fires, leaving 0 or 1 in
    # the result cell, so the ASCII offset is paid once here instead of at
    # every leaf -- which is what the whole tree used to spend most of its
    # characters on.
    move(result)
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    return "".join(cells)


# The build plan for every Collatz Multiverse constant: ``_PLAN[n]`` is
# ``(needed, decompositions)`` where ``needed`` is the smallest set of
# constants (beyond k1/k2) required to build ``k n`` and ``decompositions``
# maps each such constant to the ``(b, a, c)`` it is built from.
_PLAN: dict[int, tuple[frozenset[int], dict[int, tuple[int, int, int]]]] = {
    1: (frozenset(), {}),
    2: (frozenset(), {}),
}


def _extend_plans(maxval: int) -> None:
    """Fill ``_PLAN`` up to ``maxval`` with minimal two-line build plans.

    ``v = a x + b`` applies the Collatz rule to ``v``: odd or zero becomes
    ``v * a + b``, even halves.  A fresh register copies ``b`` with
    ``v = negativeOne x + b``; if ``b`` is odd a second line makes
    ``b * a + c``.  O(log) constants instead of a +1/+2 chain.
    """
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
    """Lines building Collatz Multiverse constants for the values in ``needed``.

    ``k1``/``k2`` bootstrap from ``negativeOne``; the rest use
    :func:`_extend_plans`'s two-line trick.  Only referenced constants are built.
    """
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
