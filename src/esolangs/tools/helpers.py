"""Shared helpers for the boolean-function program generators.

A valid table has ``2**n`` entries, so ``n`` is recovered from the length
and the generators take no ``n`` parameter.
"""

from collections.abc import Callable, Iterable, Sequence
from itertools import pairwise, repeat

from esolangs.exceptions import TruthTableError

# ``ord("0")``.  Input digits arrive as 48/49 from a byte-oriented read, and a
# result prints as ``_ASCII_ZERO + bit``, so this offset appears in every
# generator that reads or writes a digit.  Named because a bare ``48`` in a run
# of ``+`` or ``-`` reads as a magic number.
_ASCII_ZERO = 48
_ASCII_ONE = _ASCII_ZERO + 1  # ``ord("1")``, the digit the other branch prints


def grid_width(program: str) -> int:
    """Return the widest rendered row, including its padding."""
    return max(map(len, program.split("\n")))


def narrowest_grid(*candidates: str) -> str:
    """Return the narrowest layout, keeping the earlier one on a tie."""
    return min(candidates, key=grid_width)


def constant_span_test(truth_table: str) -> Callable[[int, int], bool]:
    """Return an O(1) test for whether a half-open table span is constant."""
    ones = [0]
    for bit in truth_table:
        ones.append(ones[-1] + (bit == "1"))

    def constant(start: int, stop: int) -> bool:
        count = ones[stop] - ones[start]
        return count in (0, stop - start)

    return constant


def subtree_ids(truth_table: str) -> list[list[int]]:
    """Return an id for every subtable, equal ones at a level sharing one.

    ``ids[d][k]`` names the ``k``-th subtable of ``2**(n - d)`` rows:
    ``ids[0]`` is the whole table, ``ids[n]`` its rows.  A constant subtable
    is ``0`` or ``1`` at every level, and any other id is fresh the first
    time its pair of halves turns up, so ids ascend with first occurrence
    along a level.  Built bottom-up from the child ids, one dict lookup a
    node -- the quasi-reduced decision diagram, interned rather than
    searched, in O(T).
    """
    n = _validate_truth_table(truth_table)
    level = [int(bit) for bit in truth_table]
    ids = [level]
    fresh = 2
    for _ in range(n):
        seen: dict[tuple[int, int], int] = {}
        above: list[int] = []
        for zero, one in zip(level[::2], level[1::2], strict=True):
            if zero == one and zero < 2:  # two equal constants stay one
                above.append(zero)
                continue
            if (zero, one) not in seen:
                seen[zero, one] = fresh
                fresh += 1
            above.append(seen[zero, one])
        level = above
        ids.append(level)
    ids.reverse()
    return ids


def subtree_slot(
    ids: list[list[int]], level: int, block: int, *, skip: bool
) -> tuple[int, int, tuple[int, int]]:
    """Name the subtree at ``block`` of ``level`` for a shared tree's lookup.

    With ``skip``, a test whose halves agree is passed over for its zero
    half.  The name is ``(level, id)`` for a node and ``(-1, bit)`` for a
    leaf, which is the same code at every level.
    """
    while skip and level + 1 < len(ids) and ids[level][block] >= 2:
        if ids[level + 1][2 * block] != ids[level + 1][2 * block + 1]:
            break
        level, block = level + 1, 2 * block
    key = ids[level][block]
    return level, block, (level, key) if key >= 2 else (-1, key)


class SubtreeDiagram:
    """The reduced diagram by subtree id, for a tree that hands a share down.

    ``halves[key]`` are a node's zero and one halves and ``level[key]`` its
    depth; ids are unique across levels, so an id alone names a node.  A
    generator that pushes or binds a repeated subtree once, where its copies
    all lie below, asks :meth:`reaches` whether a half still needs it and
    :meth:`repeated_near` which subtrees are worth offering.  Both memoize
    per id, so each is O(1) a node amortized for a fixed ``depth``.
    """

    def __init__(self, truth_table: str) -> None:
        """Intern ``truth_table``'s subtrees and index each node's halves."""
        self.ids = subtree_ids(truth_table)
        self.halves: dict[int, tuple[int, int]] = {}
        self.level: dict[int, int] = {}
        for depth, (row, under) in enumerate(pairwise(self.ids)):
            for block, key in enumerate(row):
                if key >= 2 and key not in self.halves:
                    self.halves[key] = (under[2 * block], under[2 * block + 1])
                    self.level[key] = depth
        self._reach: dict[tuple[int, int], bool] = {}
        self._counts: dict[tuple[int, int], dict[int, int]] = {}

    def reaches(self, key: int, target: int) -> bool:
        """Whether node ``target`` is ``key`` or lies below it."""
        if key == target:
            return True
        if key < 2 or self.level[key] >= self.level[target]:
            return False
        if (key, target) not in self._reach:
            halves = set(self.halves[key])
            found = any(self.reaches(half, target) for half in halves)
            self._reach[key, target] = found
        return self._reach[key, target]

    def _count(self, key: int, depth: int) -> dict[int, int]:
        """Count each node within ``depth`` levels below, equal halves once."""
        if key < 2 or not depth:
            return {}
        if (key, depth) not in self._counts:
            found: dict[int, int] = {}
            for half in set(self.halves[key]):
                below = self._count(half, depth - 1).items()
                for name, count in [(half, 1), *below]:
                    if name >= 2:
                        found[name] = found.get(name, 0) + count
            self._counts[key, depth] = found
        return self._counts[key, depth]

    def repeated_near(self, key: int, depth: int) -> list[int]:
        """Return the nodes met twice or more within ``depth`` levels below."""
        return [name for name, count in self._count(key, depth).items() if count > 1]


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


def mark_runs(template: str, char: str, setters: Setters) -> str:
    """Return the template as a wrapper is handed it.

    Runs of ``char`` are each as long as their input's setters, so no
    separator is needed; each is re-spelled as its own :func:`mark`, the form
    a wrapper keeps whole.  ``char`` is the *language's* template character
    and cannot default to :data:`TEMPLATE_CHAR`: INTERCAL embeds on ``@``
    because ``$`` is its mingle operator, so scanning for the global one
    found an operator and read it as a one-character run.
    """
    out, position = [], 0
    for i, (start, end) in enumerate(runs(template, char, setters)):
        out.append(template[position:start] + mark(i) * (end - start))
        position = end
    return "".join(out) + template[position:]


def unmark(text: str, char: str, inputs: int) -> str:
    """Return ``text`` with every input's mark replaced by ``char``."""
    return text.translate({MARK + i: char for i in range(inputs)})


def runs(text: str, char: str, setters: Setters) -> list[tuple[int, int]]:
    """Return the ``[start, end)`` of each input's run in ``text``.

    Runs are consumed left to right in setter widths, and every ``char``
    must belong to one; a width-zero setter (an ignored input) has
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


def _residual_ids(
    truth_table: str, n: int
) -> tuple[list[list[int]], dict[int, tuple[int, int]], dict[int, int | None]]:
    """Canonical residual IDs, children and constant values in O(T) RAM work."""
    levels: list[list[int]] = [[] for _ in range(n + 1)]
    ids = [1 if bit == "1" else 0 for bit in truth_table]
    levels[n] = list(dict.fromkeys(ids))
    children: dict[int, tuple[int, int]] = {}
    constants: dict[int, int | None] = {0: 0, 1: 1}
    serial = 2
    for k in range(n - 1, -1, -1):
        names: dict[tuple[int, int], int] = {}
        parents = []
        for zero, one in zip(ids[::2], ids[1::2], strict=True):
            pair = (zero, one)
            if pair not in names:
                names[pair] = serial
                children[serial] = pair
                constants[serial] = (
                    constants[zero] if constants[zero] == constants[one] else None
                )
                serial += 1
            parents.append(names[pair])
        levels[k] = list(names.values())
        ids = parents
    return levels, children, constants


def deque_plan(order: tuple[int, ...]) -> tuple[list[bool], list[bool]] | None:
    """Return head pushes by input and head pops by level that pop ``order``.

    Inputs are read in order and each goes to the row's head or tail, so
    the row reads (head first) the head-pushed inputs descending, input 0,
    then the tail-pushed ones ascending; the tree pops either end at each
    level.  Before input 0 is popped each pop is the largest left on its
    side, so that prefix splits into two descending runs, the tail run
    above every input popped after 0; those are all tail-pushed, so they
    leave the row as a run each pop takes the least or the greatest of.
    ``None`` when ``order`` has no such split: the plan is the greedy fit
    (a tie goes to the lower run), which finds every poppable order.
    """
    depth = len(order)
    zero = order.index(0)
    floor = max(order[zero + 1 :], default=-1)
    head_push = [False] * depth
    head_pop = []
    last = {True: depth, False: depth}
    for x in order[:zero]:
        fits = [
            head for head in (True, False) if x < last[head] and (head or x > floor)
        ]
        if not fits:
            return None
        head = min(fits, key=last.__getitem__)
        last[head] = x
        head_push[x] = head
        head_pop.append(head)
    head_pop.append(True)
    rest = sorted(order[zero + 1 :])
    for x in order[zero + 1 :]:
        if x not in (rest[0], rest[-1]):
            return None
        head_pop.append(x == rest[0])
        rest.remove(x)
    return head_push, head_pop


def essential_inputs(truth_table: str, n: int) -> list[int]:
    """Input positions affecting the table, with O(T) worst-case RAM work.

    Slice comparisons stop early on dense tables. After four table lengths
    of comparisons, canonical child IDs bound the remaining work instead.
    """
    budget = 4 * len(truth_table)
    result = []
    for i in range(n):
        half = 1 << (n - 1 - i)
        block = 2 * half
        for lo in range(0, len(truth_table), block):
            if block > budget:
                if truth_table.count(truth_table[0]) == len(truth_table):
                    return []
                levels, children, _ = _residual_ids(truth_table, n)
                return [
                    k
                    for k in range(n)
                    if any(children[s][0] != children[s][1] for s in levels[k])
                ]
            budget -= block
            if truth_table[lo : lo + half] != truth_table[lo + half : lo + block]:
                result.append(i)
                break
    return result


def _depends_on(truth_table: str, half: int) -> bool:
    """Whether some block of ``2 * half`` rows has unequal halves."""
    block = 2 * half
    return any(
        truth_table[lo : lo + half] != truth_table[lo + half : lo + block]
        for lo in range(0, len(truth_table), block)
    )


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
    return {perm[k] for k in range(n) if _depends_on(truth_table, 1 << (n - 1 - k))}


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


# The walker only lays tokens out and measures runs of them, never looks
# inside one, so a token is whatever the caller finds convenient: a string
# for most generators, an instruction tuple for S*bleq.
type Leaf[Token] = Callable[[int, int], list[Token]]
type Node[Token] = Callable[[int, int, int, int], list[Token]]


def decision_tree_tokens[Token](
    truth_table: str,
    leaf: Leaf[Token],
    node: Node[Token],
    *,
    parent_width: int | Callable[[int], int] = 0,
    start: int = 0,
    collapse: bool = False,
) -> list[Token]:
    """Walk a truth table's decision tree, laying out caller-emitted parts.

    ``leaf(level, row)`` returns a leaf's tokens; ``node(level, zero, one,
    at)`` returns a node's own ``parent_width`` tokens given its finished
    subtrees' *lengths*, post-order; they sit ahead of the zero subtree,
    then the one subtree.  ``collapse`` returns a leaf as soon as a
    subtree's rows agree.  ``at`` is the absolute index the subtree begins
    at, from ``start`` and ``parent_width`` (a constant or a function of
    level, as RAM0's address run), which is what lets Bitdeque, RAM0 and
    S*bleq name a jump target up front instead of backpatching.  One flat
    list, a node's slot written in after its subtrees: O(tokens).

    Deliberately cannot: act between the children (6-5, Jaune allocate a
    label there; Polynomial threads a cell value); thread
    anything *down* (CV(N)(C)'s accumulator, Jaune's held bit, Circlefuck's
    pointer); lay the one subtree first (Between, CV(N)(C), Unsquare); split
    other than MSB-first (Modulous, Unsquare); build a
    positional heap (Eval, Forth pin children at ``2i+1``/``2i+2``); skip a
    child (AddSubJump, Jaune descend into one half -- 24 of 256 tables came
    out longer at ``n == 3``); Lamfunc's plain string; the grid generators'
    plane.  Contrast :func:`decision_tree_body`, which carries a whole
    construction rather than a walk its caller fills in.
    """
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)
    width = parent_width if callable(parent_width) else lambda _level: parent_width
    out: list[Token] = []

    def walk(level: int, lo: int, hi: int, at: int) -> None:
        if level == n or (collapse and constant(lo, hi)):
            out.extend(leaf(level, lo))
            return
        half = (hi - lo) // 2
        slot = len(out)
        own = width(level)
        out.extend(repeat(None, own))  # type: ignore[arg-type]
        below = at + own
        walk(level + 1, lo, lo + half, below)
        zero = len(out) - slot - own
        walk(level + 1, lo + half, hi, below + zero)
        one = len(out) - slot - own - zero
        out[slot : slot + own] = node(level, zero, one, at)

    walk(0, 0, len(truth_table), start)
    return out


def move_text(start: int, target: int, right: str, left: str) -> str:
    """Return the moves taking a one-dimensional pointer to ``target``.

    One run, not one token per cell, so a caller measuring maximal runs --
    Factor, which pays a prime per run -- sees the same count either way.
    """
    delta = target - start
    return right * delta if delta >= 0 else left * -delta


def decision_tree_body(
    truth_table: str,
    right: str,
    left: str,
    perm: tuple[int, ...],
    start: int,
    *,
    binary_leaves: bool = False,
    result: int | None = None,
) -> tuple[str, int]:
    """Return the decision tree alone, and the cell it leaves the pointer on.

    The reads above it and the print below it are the caller's.  Split out
    for Factor, which pays a prime per maximal run rather than a character
    per command, and so wants to fold the ASCII offsets the reads and the
    print would otherwise spend 48 characters on each.
    :func:`_decision_tree_program` joins the three parts back.
    ``binary_leaves`` transfers the final bit directly into the answer.
    """
    n = _validate_truth_table(truth_table)

    cells: list[str] = []
    pos = start

    def move(target: int) -> None:
        nonlocal pos
        cells.append(move_text(pos, target, right, left))
        pos = target

    result = 2 * n if result is None else result
    is_constant = constant_span_test(truth_table)

    def constant(i: int, combo: int) -> str | None:
        """Return the shared value of the subtree at ``(i, combo)``, else None."""
        span = 2 ** (n - i)
        return truth_table[combo] if is_constant(combo, combo + span) else None

    def branch(i: int, combo: int) -> None:
        """Emit one side of node ``i``: a leaf when constant, else a subtree."""
        value = constant(i + 1, combo)
        if value is None:
            move(2 * perm[i + 1])
            node(i + 1, combo)
        elif value == "1":
            move(result)
            cells.append("+")

    def node(i: int, combo: int) -> None:
        """Emit node ``i``: test ``b_i``, run one side, leave both cells zero."""
        bit = 2 * perm[i]
        if binary_leaves and i == n - 1:
            if truth_table[combo] == truth_table[combo + 1]:
                if truth_table[combo] == "1":
                    move(result)
                    cells.append("+")
                return
            move(bit)
            if truth_table[combo] == "1":
                move(result)
                cells.append("+")
                move(bit)
            cells.append("[-")
            move(result)
            cells.append("+" if truth_table[combo + 1] == "1" else "-")
            move(bit)
            cells.append("]")
            return
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
    return "".join(cells), pos


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


def _cm_constants(needed: Iterable[int], zero: str = "zero") -> list[str]:
    """Lines building Collatz Multiverse constants for the values in ``needed``.

    ``k1``/``k2`` bootstrap from ``negativeOne``; the rest use
    :func:`_extend_plans`'s two-line trick.  Only referenced constants are built.

    ``zero`` names the never-written register the language reads as 0.  It is
    a parameter because the name is free -- any register never assigned reads
    as 0 -- and a caller that spells zero on most of its lines wants the
    shortest spelling.
    """
    need = sorted(n for n in set(needed) if n > 2)
    lines = [
        "k1 = negativeOne x + negativeOne, NOT PRINT.",
        f"k1 = negativeOne x + {zero}, NOT PRINT.",
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
                lines.append(f"k{n} = k{a} x + {zero}, NOT PRINT.")
            else:
                lines.append(f"k{n} = k{a} x + k{c}, NOT PRINT.")
    return lines


def _parity_bias(truth_table: str) -> int | None:
    """Return the complement bit for parity, or None, in O(T)."""
    bias = int(truth_table[0])
    parity = bytearray(len(truth_table))
    for row in range(1, len(truth_table)):
        parity[row] = parity[row >> 1] ^ (row & 1)
        if int(truth_table[row]) != parity[row] ^ bias:
            return None
    return bias
