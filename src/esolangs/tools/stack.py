"""Boolean-function generators for stack-based languages."""

from functools import cache
from itertools import pairwise, product

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    permute_truth_table,
    read_at,
)

#: One sink choice: how far a freshly-read bit drops, and the ops that do it.
Sinks = tuple[tuple[int, str], ...]


def _sink_top(stack: tuple[int, ...], places: int) -> tuple[int, ...]:
    """Move the top bit down by ``places``, leaving the others in order."""
    *below, top = stack
    at = len(below) - places
    return (*below[:at], top, *below[at:])


def stack_programs(n: int, sinks: Sinks, read: str) -> dict[tuple[int, ...], str]:
    """Read-and-sink program for each reachable stack arrangement.

    Maps each arrangement (bottom to top, by input index) to its program.
    A product, not a search: a read leaves its bit on top and the only
    lasting choice is how far it sinks (0, 1 or 2), so there are
    ``2 * 3**(n - 2)`` arrangements, which a test pins.  Shared by Forþ and
    Unsquare via ``sinks`` (``(places, ops)``) and ``read``.
    """
    reached: dict[tuple[int, ...], str] = {}
    for combination in product(sinks, repeat=n):
        stack: tuple[int, ...] = ()
        text = ""
        for read_index, (places, ops) in enumerate(combination):
            stack = (*stack, read_index)
            text += read
            if places >= len(stack):
                break  # nothing below to sink under
            stack = _sink_top(stack, places)
            text += ops
        else:
            # Every surviving sink combination lands on a distinct stack
            # shape -- 162 completions at n == 6, no repeat -- so the
            # shorter-text tie-break never fires.  It stays because the
            # table is keyed by shape, and a future sink whose shape
            # repeated would need it to keep the cheaper spelling.
            if (  # pragma: no branch - no two combinations share a shape
                stack not in reached or len(text) < len(reached[stack])
            ):
                reached[stack] = text
    return reached


def _grapheme_push0() -> str:
    """Grapheme code pushing the integer 0 (``Z`` is intmode's zero digit)."""
    return "FZF"


def _grapheme_push1() -> str:
    """Grapheme code pushing the integer 1 (``10 / 10``)."""
    return "FAF" + "FAF" + "R"


def _grapheme_push65() -> str:
    """Grapheme code pushing 65 (``ord('A')``, the input normalization constant)."""
    return "FAF" + "FEF" + "R" + "FGF" + "B"  # 70 - (50 / 10)


#: The reserved variable key, holding the 65 that normalizes an input bit.
_GRAPHEME_CONST_KEY = 90


def _grapheme_slot_key(slot: int) -> int:
    """Return the unbounded integer key holding input ``slot``."""
    key = 10 * (slot + 1)
    return key if key < _GRAPHEME_CONST_KEY else key + 10


def _grapheme_push_key(key: int) -> str:
    """Grapheme code pushing the integer variable key ``key`` (a multiple of 10)."""
    # Int mode computes an ordinary decimal value followed by one zero, but
    # ``F`` closes the mode and therefore cannot spell digit 6.  Split each 6
    # into 1 + 5; the two literals have disjoint nonzero columns, so their sum
    # is exactly the requested key with no carries.  This replaces the old
    # one-letter alphabet's 24-key ceiling without changing the value model.
    digits = str(key // 10)
    letters = "ZABCDE?GHI"

    def literal(value: str) -> str:
        return "F" + "".join(letters[int(digit)] for digit in value) + "F"

    if "6" not in digits:
        return literal(digits)
    low = "".join("1" if digit == "6" else digit for digit in digits)
    five = "".join("5" if digit == "6" else "0" for digit in digits)
    return literal(low) + literal(five) + "A"


def _grapheme_push_int(value: int) -> str:
    """Push any nonnegative integer using Grapheme's trailing-zero literals."""
    return _grapheme_push_key(10) + _grapheme_push_key(value * 10) + "R"


def grapheme(truth_table: str) -> str:
    """Build a Grapheme program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; prints
    ``'0'`` or ``'1'``.  ``W`` reads a whole line and every non-empty string
    is truthy, so the harness feeds ``A`` (one) and ``%`` (zero), normalized
    by ``W 65 B T`` and stored; a folded decision tree follows, with ``V``
    skipping the unselected branch by character length.  The most repeated,
    deepest inputs get the shortest keys.  A leaf pushes its bit; ``Y`` prints.
    """
    n = _validate_truth_table(truth_table)

    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    width = len(used)
    level_of = {input_index: level for level, input_index in enumerate(used)}
    slots = [width - 1 - level for level in range(width)]

    head = [_grapheme_push65() + _grapheme_push_key(_GRAPHEME_CONST_KEY) + "C"]
    for input_index in range(n):
        if input_index not in level_of:
            head.append("W")
            continue
        slot = slots[level_of[input_index]]
        head.append(
            "W"
            + _grapheme_push_key(_GRAPHEME_CONST_KEY)
            + "D"
            + "B"
            + "T"
            + _grapheme_push_key(_grapheme_slot_key(slot))
            + "C"
        )

    changes = [0]
    for previous, current in pairwise(table):
        changes.append(changes[-1] + (previous != current))

    # One flat piece list: a node's two skips depend on its subtrees'
    # lengths, so each is a slot reserved ahead and written once the
    # subtree is down -- O(T) rather than a copy per level.
    body: list[str] = []

    def tree(start: int, end: int, depth: int) -> int:
        """Lay the subtree down and return its length in characters."""
        if changes[start] == changes[end - 1]:
            leaf = _grapheme_push1() if table[start] == "1" else _grapheme_push0()
            body.append(leaf)
            return len(leaf)
        half = (start + end) // 2
        conditional = len(body)
        body.append("")
        zero_len = tree(start, half, depth + 1)
        skip = len(body)
        body.append("")
        one_len = tree(half, end, depth + 1)
        always = _grapheme_push_int(one_len) + _grapheme_push0() + "V"
        lookup = _grapheme_push_key(_grapheme_slot_key(slots[depth])) + "D"
        body[skip] = always
        body[conditional] = _grapheme_push_int(zero_len + len(always)) + lookup + "TV"
        return len(body[conditional]) + zero_len + len(always) + one_len

    tree(0, 1 << width, 0)
    return "".join([*head, *body, "Y"])


def _forth_const(value: int) -> str:
    """Forþ code pushing ``value`` (base-15 digits built with Horner's rule)."""
    digits = "0123456789ABCDEF"
    if value == 0:
        return "0"
    ds: list[int] = []
    v = value
    while v:
        ds.append(v % 15)
        v //= 15
    ds.reverse()
    prog = digits[ds[0]]
    for d in ds[1:]:
        prog += "F*" + digits[d] + "+"
    return prog


def forth(truth_table: str) -> str:
    """Build a Forþ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; prints
    ``'0'`` or ``'1'``.  A decision tree of functions: ``{ scope }`` stores,
    ``;`` calls; inputs normalized with ``,68*-``; a leaf pushes
    ``48 + result`` for the final ``.``.  Heap indices (children of ``m`` at
    ``2m + 1``, ``2m + 2``) are never spelled: ``{`` reads its key without
    popping, so definitions are emitted in index order introduced by
    ``1+``, and ``;`` pops, so a node that dups its key leaves the callee
    its own index -- an internal node is the fixed ``2*1++:;``.  Linear in
    the table.  A constant subtree answers in place and its numbering gap
    is a scope that never exists.  ``;`` pops, so the last input is tested
    first; that order is kept.
    """
    n = _validate_truth_table(truth_table)
    # ``;`` pops, so the tree tests the *last* input at the root: the order
    # this generator has always emitted is the reversal, not the identity.
    # It goes first and ties keep it, so a table no reorder helps emits
    # exactly what it emitted before.
    natural = tuple(reversed(range(n)))
    return _forth_ordered(permute_truth_table(truth_table, natural), natural)


# The read that pushes one normalized input bit.
_FORTH_READ = ",68*-"


#: One internal node, whole.  Entering it the stack is ``.. bit, index``:
#: ``2*1+`` turns the index into the base of its two children, ``+`` adds the
#: bit (selecting one of them, and consuming the bit), ``:`` keeps a copy so
#: the callee can do the same, and ``;`` calls.  Constant at every depth,
#: which is the whole reason the construction is linear.
_FORTH_DISPATCH = "2*1++:;"


# How far a freshly-read bit can sink, and the ops that put it there.  ``v``
# swaps the top two and ``c`` rotates the third up, so two ``c``s bury the
# new bit under the two below it.  ``o`` is unusable and absent deliberately:
# it reverses the *whole* stack, which would drag the scope indices sitting
# under the bits up with them.
_FORTH_SINKS = ((0, ""), (1, "v"), (2, "cc"))


@cache
def _forth_stack_programs(n: int) -> dict[tuple[int, ...], str]:
    """Read-and-rotate program for each reachable stack arrangement.

    ``2 * 3**(n - 2)`` arrangements, as :func:`stack_programs`.  Sinking
    each bit as it arrives (not after all reads, which permutes only the last
    three: 2.4% saving at n == 4, none at n == 5) reaches 18 at n == 4 and 54
    at n == 5.  A BFS finds shorter op strings on some arrangements (a late
    ``c`` composes across reads); not used, the natural order is kept.
    """
    return stack_programs(n, _FORTH_SINKS, _FORTH_READ)


def _forth_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Forþ program; see :func:`forth`.

    ``truth_table`` is already permuted; ``perm`` surfaces only in the
    arrangement the reads must produce (level ``k`` needs ``perm[k]`` on
    top).  Returns ``""`` when unreachable.  The stack is balanced by
    construction and must be: an empty pop halts Forþ, and the definition
    counter sits under the bits.  Each dispatch consumes one bit and one
    index and produces one index.
    """
    n = _validate_truth_table(truth_table)
    wanted = tuple(reversed(perm))
    reads = (
        _FORTH_READ * n
        if wanted == tuple(range(n))
        else _forth_stack_programs(n).get(wanted)
    )
    if reads is None:
        return ""

    last_internal = 2**n - 2
    constant = constant_span_test(truth_table)

    def span_under(m: int) -> tuple[int, int]:
        """Return the table rows the subtree rooted at heap index ``m`` covers.

        Heap index ``m`` at depth ``d`` is the ``m - (2**d - 1)``-th node of
        its level, and covers that many spans of ``2**(n - d)`` rows in; the
        leaf at heap index ``m`` is row ``m - last_internal - 1``.  O(1), so
        the fold test over the whole heap is O(2**n).
        """
        depth = (m + 1).bit_length() - 1
        width = 1 << (n - depth)
        lo = (m - (1 << depth) + 1) * width
        return lo, lo + width

    prog = []
    folded: set[int] = set()
    previous = 0  # the index the accumulator holds; 0 before anything is pushed
    for m in range(1, 2 ** (n + 1) - 1):
        if m in folded:
            # An ancestor already answered for this subtree, so its scope is
            # never called.  Forþ stores scopes in a dict keyed by the
            # pushed number and looks them up with a default, so a gap in
            # the numbering costs nothing -- the node simply never exists.
            continue
        if m <= last_internal:
            lo, hi = span_under(m)
            if constant(lo, hi):
                # Every row under this node agrees, so the bits it would
                # branch on cannot change the answer: answer here and drop
                # the whole subtree.  The inputs are read up front, outside
                # the tree, so a folded program still consumes its input
                # exactly as an unfolded one does.
                body = _forth_const(_ASCII_ZERO + int(truth_table[lo]))
                # Drop the *whole* subtree, not just the two children: a
                # grandchild is just as unreachable, and marking one level
                # leaves the deeper nodes emitted but never called.
                below = [2 * m + 1, 2 * m + 2]
                while below:
                    child = below.pop()
                    folded.add(child)
                    if child <= last_internal:
                        below += [2 * child + 1, 2 * child + 2]
            else:  # internal node: dispatch on the top bit
                body = _FORTH_DISPATCH
        else:  # leaf: push the result byte
            body = _forth_const(_ASCII_ZERO + int(truth_table[m - last_internal - 1]))
        # The label is a step from the index already on the stack, never the
        # index itself: ``{`` reads its key without popping, so the pushed
        # number survives the definition and the next one is ``+`` away.
        step = _forth_const(m - previous) + ("+" if previous else "")
        previous = m
        prog.append(step + "{" + body + "}")
    prog.append(reads)  # the reads, with this order's rotations woven in
    prog.append("1+:;.")  # root dispatch, then print the result
    return "".join(prog)


def modulous(truth_table: str) -> str:
    """Build a Modulous program: a table literal popped down to its row."""
    n = _validate_truth_table(truth_table)
    # ``PSH STR`` pushes the characters in reverse, so the leftmost entry is
    # the one on top and discarding ``index`` of them uncovers
    # ``truth_table[index]`` -- the row index read most significant bit
    # first, which is what the weights below build.  The first read *is* the
    # counter: a bit is already 0 or 1, so the top weight is one conditional
    # ``ADD`` away and no accumulator is pushed.
    top = 1 << (n - 1)
    reads = ["[INP INT]" + (f"[JMP F 2 IF 0][ADD {top - 1}]" if n > 1 else "")]
    reads += [
        f"[INP INT][JMP F 4 IF 0][POP][ADD {1 << (n - 1 - i)}][JMP F 2][POP]"
        for i in range(1, n)
    ]
    # ``SWP``/``POP`` discards the entry *under* the counter, which is what
    # keeps the counter reachable: nothing but the top two cells is.
    walk = "[JMP F 5 IF 0][SUB 1][SWP][POP][JMP B 4][POP][PRT][END]"
    return f'[PSH STR "{truth_table}"]{"".join(reads)}{walk}'


def _bfstack_encoder(n: int, *, preset: bool) -> str:
    """BFStack code turning the n inputs into the number ``1 + sum(bit*2^k)``.

    ``,`` reads, 48 ``-``s normalize, ``[<+w>]`` adds the weight.  The ``+1``
    keeps the result nonzero so the decoder's outer ``[`` always runs.
    ``preset`` starts the result at 1 for the subtracting decoder.
    """
    # Result cell (0, or 1 when the decoder subtracts) below the accumulator.
    prog = ">+>+" if preset else ">>+"
    for k in range(n):
        weight = 2 ** (n - 1 - k)
        prog += "," + "-" * _ASCII_ZERO + "[" + "<" + "+" * weight + ">" + "]" + "<"
    return prog


def _bfstack_cascade(rows: list[int], payload: str) -> str:
    """Nest subtractions over ``rows``, running ``payload`` off the list.

    Reaching zero on a listed row leaves that row's ``[`` unentered, so
    ``payload`` runs exactly when the encoded number is not in ``rows``.
    """
    if not rows:
        return payload
    prog = "["
    prev = 0
    for row in rows:
        prog += "-" * (row - prev) + "["
        prev = row
    return prog + payload + "]" * (len(rows) + 1)


def _bfstack_decoder(truth_table: str) -> tuple[str, bool]:
    """Return the decoder, and whether the result must start at 1.

    A listed row costs the gap to the one before it and two brackets, so
    listing the *zero* rows made a mostly-zero table the expensive case --
    backwards, the all-zero function being the cheapest there is: at twelve
    inputs it cost 17,091 characters against 4,801 for the all-one table.
    Listing the one rows instead inverts the cascade, which starting the
    result at 1 and subtracting undoes.  Ties keep the direct form.
    """
    zeros = [k + 1 for k, ch in enumerate(truth_table) if ch == "0"]
    ones = [k + 1 for k, ch in enumerate(truth_table) if ch == "1"]
    direct = _bfstack_cascade(zeros, "[<+>]")
    # One character dearer than it looks: the preset ``+`` in the encoder.
    inverted = _bfstack_cascade(ones, "[<->]")
    if len(inverted) + 1 < len(direct):
        return inverted, True
    return direct, False


def bfstack(truth_table: str) -> str:
    """Build a BFStack program computing the given truth table.

    No branching: encode the inputs as ``1 + sum(bit*2^k)``, then nested
    ``[`` loops single out the rows of whichever result value is rarer.
    """
    n = _validate_truth_table(truth_table)
    decoder, preset = _bfstack_decoder(truth_table)
    return _bfstack_encoder(n, preset=preset) + decoder + "<" + "+" * _ASCII_ZERO + "."


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.
    ``>``/``<`` loops while the accumulator is neither 0 nor 1, so ``x``
    makes a bit a loop condition and ``x->IA<`` its negation; inputs are
    reduced by ``>-<`` and pushed; a run branch ends ``IA`` so the sibling's
    guard skips, and a leaf pushes ``48 + entry`` for the final ``o``.
    ``A`` pops, so the natural order tests the last input first.  Reordering
    was wrongly excluded (``S`` swaps only the top two): the accumulator is
    a second place to hold a bit, so ``A``/``S``/``P`` sink one two places
    (:data:`_UNSQUARE_SINKS`).  At each read the generator greedily sinks
    the new bit 0, 1 or 2 places, priced by :class:`_UnsquarePricer`
    incrementally (``O(T)`` for the order; from scratch was ``O(nT)`` each).
    """
    n = _validate_truth_table(truth_table)
    # A zero-place sink is always a candidate, so each greedy choice is no
    # larger under the exact model than leaving that input in natural order.
    stack: tuple[int, ...] = ()
    prefix = ""
    pricer = _UnsquarePricer(truth_table, n)
    for input_index in range(n):
        pushed = (*stack, input_index)
        choices: list[tuple[int, int, tuple[int, ...], str]] = []
        for places, ops in _UNSQUARE_SINKS:
            if places >= len(pushed):
                continue
            arranged = _sink_top(pushed, places)
            candidate_prefix = prefix + _UNSQUARE_READ + ops
            future_prefix = candidate_prefix + _UNSQUARE_READ * (n - input_index - 1)
            cost = len(future_prefix) + pricer.price(input_index, places) + 1
            choices.append((cost, places, arranged, ops))
        _, places, stack, ops = min(choices)
        pricer.commit(input_index, places)
        prefix += _UNSQUARE_READ + ops
    table = permute_truth_table(truth_table, stack)
    return prefix + _unsquare_tree(table, n)


# The read that pushes one normalized input bit.
_UNSQUARE_READ = "iA>-<P"

# How far a freshly-read bit can sink, and the ops that put it there.  ``S``
# swaps the top two.  Sinking two places is ``SASP``, not ``ASP``: ``A``
# lifts the *top* out and ``S`` then swaps the pair beneath it, so ``ASP``
# reorders those two and puts the bit back where it started.  The leading
# ``S`` is what moves the bit down first, so the pair it must cross ends up
# above it.  Nothing reaches three places: ``S`` sees only the top two and
# the accumulator holds one value, so a third would need somewhere to put
# the bit already in it.
_UNSQUARE_SINKS = ((0, ""), (1, "S"), (2, "SASP"))


class _UnsquarePricer:
    """Exact tree sizes for the greedy's candidates, one read at a time.

    The tree tests the natural inputs top-down, then the arranged ones from
    the stack top; ``levels[d]`` holds each node's constant value (``-1``
    mixed) and cost (29 constant, 17 plus halves).  Sinking ``s`` places
    shifts the old levels down by one, so only the top ``s + 1`` levels and
    the natural part are re-merged, ``O(T / 2**k)`` at read ``k``.
    """

    def __init__(self, truth_table: str, n: int) -> None:
        self.n = n
        self.levels: list[tuple[dict[int, int], dict[int, int]]] = [
            (
                {row: int(entry) for row, entry in enumerate(truth_table)},
                dict.fromkeys(range(len(truth_table)), 29),
            )
        ]
        self.stack: tuple[int, ...] = ()

    def _merge(
        self, level: tuple[dict[int, int], dict[int, int]], test: int
    ) -> tuple[dict[int, int], dict[int, int]]:
        """Return the level above ``level`` when ``test`` is the input tested there."""
        bit = 1 << (self.n - 1 - test)
        values, costs = level
        merged_values: dict[int, int] = {}
        merged_costs: dict[int, int] = {}
        for node, low in values.items():
            if node & bit:
                continue
            high = values[node | bit]
            if low == high and low != -1:
                merged_values[node] = low
                merged_costs[node] = 29
            else:
                merged_values[node] = -1
                merged_costs[node] = 17 + costs[node] + costs[node | bit]
        return merged_values, merged_costs

    def _rebuilt(
        self, input_index: int, places: int
    ) -> list[tuple[dict[int, int], dict[int, int]]]:
        """Return the arranged levels after sinking ``input_index`` by ``places``."""
        arranged = _sink_top((*self.stack, input_index), places)
        levels = self.levels[places:]  # old depth ``places`` is new ``places + 1``
        for depth in range(places, -1, -1):
            # Depth ``d`` tests the arranged input ``places`` from the top...
            tested = arranged[len(arranged) - 1 - depth]
            levels = [self._merge(levels[0], tested), *levels]
        return levels

    def price(self, input_index: int, places: int) -> int:
        """Return the tree's cost with ``input_index`` sunk ``places`` deep."""
        level = self._rebuilt(input_index, places)[0]
        for natural in range(input_index + 1, self.n):
            level = self._merge(level, natural)
        return level[1][0]

    def commit(self, input_index: int, places: int) -> None:
        """Adopt the chosen sink for the next read."""
        self.levels = self._rebuilt(input_index, places)
        self.stack = _sink_top((*self.stack, input_index), places)


def _unsquare_tree(truth_table: str, n: int) -> str:
    """Emit the decision tree for an already-permuted table; see :func:`unsquare`.

    Bit ``k`` of a row index is the input at level ``k``; the stack prefix
    has put the bits where the pops find them.  Read through the
    bit-reversed index each subtree is a contiguous span, so the tree walks
    spans of the reflected table with an O(1) constant test into one flat
    piece list: O(2**n).
    """
    flip = "x->IA<"
    reflected = "".join(
        truth_table[int(f"{row:0{n}b}"[::-1], 2)] for row in range(2**n)
    )
    constant = constant_span_test(reflected)
    pieces: list[str] = []

    def leaf(value: str) -> str:
        return ("IA" if value == "1" else "OA") + "+" * 24 + "P" + "OA"

    def build(lo: int, hi: int) -> None:
        if constant(lo, hi):
            pieces.append(leaf(reflected[lo]))
            return
        mid = (lo + hi) // 2
        pieces.append("Ax>")
        build(mid, hi)
        pieces.append(f"IA<{flip}x>")
        build(lo, mid)
        pieces.append("OA<")

    build(0, 2**n)
    pieces.append("o")
    return "".join(pieces)
