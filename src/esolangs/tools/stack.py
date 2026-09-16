"""Boolean-function generators for stack-based languages."""

from functools import cache
from itertools import pairwise, product

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
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

    Returns the arrangement (bottom to top, by input index) mapped to the
    program producing it; an absent arrangement is one the ops cannot reach.

    **The reachable set is a product, not a search.**  A read leaves its bit
    on top, and the only choice that outlasts the next read is how far that
    bit sinks -- 0, 1 or 2 places, since neither language's ops reach
    deeper.  Composing one choice per read therefore enumerates every
    arrangement, ``2 * 3**(n - 2)`` of them, which a test pins.

    Shared by Forþ and Unsquare, whose stacks differ only in how a sink is
    spelled: ``sinks`` is the ``(places, ops)`` table and ``read`` the code
    that pushes one normalized bit.  The two callers' docstrings record
    *different* findings about the same enumeration and stay where they are.
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
    return "FGF" + "FEF" + "FAF" + "R" + "B"  # 70 - (50 / 10)


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
    return _grapheme_push_key(value * 10) + _grapheme_push_key(10) + "R"


def grapheme(truth_table: str) -> str:
    """Build a Grapheme program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Grapheme reads a whole line with ``W`` and every non-empty string is
    truthy, so the generator uses a two-character input alphabet instead of
    ``'0'``/``'1'``: the harness feeds ``A`` for a one bit and ``%`` for a
    zero.  Each bit is normalized to the integer 0/1 with ``W 65 B T``
    (``B`` computes ``ord(bit) - 65``, which is 0 exactly for ``A``, and
    ``T`` maps zero to 1 and nonzero to 0), stored in a variable, and the
    table is evaluated by a folded decision tree. ``V`` skips the unselected
    branch by its character length, so subtrees stay inline and need no
    widening variable keys. The most repeated, deepest inputs occupy the
    shortest keys. A leaf pushes its bit and ``Y`` prints it.
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

    def tree(start: int, end: int, depth: int) -> tuple[list[str], int]:
        if changes[start] == changes[end - 1]:
            leaf = _grapheme_push1() if table[start] == "1" else _grapheme_push0()
            return [leaf], len(leaf)
        half = (start + end) // 2
        zero, zero_len = tree(start, half, depth + 1)
        one, one_len = tree(half, end, depth + 1)
        always = _grapheme_push_int(one_len) + _grapheme_push0() + "V"
        lookup = _grapheme_push_key(_grapheme_slot_key(slots[depth])) + "D"
        conditional = _grapheme_push_int(zero_len + len(always)) + lookup + "TV"
        parts = [conditional, *zero, always, *one]
        return parts, sum(map(len, parts))

    body, _length = tree(0, 1 << width, 0)
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

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Forþ reads a line with ``,`` and has no clean pop, so the generator
    builds a decision tree out of functions: ``{ scope }`` stores a scope in
    the function table and ``;`` calls the one its key names.  Each input is
    read and normalized to 0/1 with ``,68*-``, and a leaf pushes
    ``48 + result`` which the final ``.`` prints.

    **Every number the tree names is a step, not an address.**  Nodes take
    heap indices -- the children of ``m`` are ``2m + 1`` and ``2m + 2`` --
    and spelling those out is what the construction avoids, because there
    are ``2**(n + 1)`` of them and a base-15 literal for one costs
    ``O(n)``.  Two properties of the language make the index implicit
    instead:

    - ``{`` reads its key without popping, so one pushed number labels a
      definition and is still there for the next.  The definitions are
      emitted in increasing index order and each is introduced by the step
      to it -- ``1+`` between adjacent nodes -- so the whole table of
      scopes is written with a running counter.
    - ``;`` pops, so a node that dups its key before calling leaves the
      callee its *own* index on the stack, under nothing but the bits still
      unread.  An internal node is then the fixed string ``2*1++:;``: it
      doubles its index for the child base, adds the bit below it (which is
      the dispatch, and consumes the bit), dups, and calls.

    The result is that no node's cost depends on where it sits, and the
    program is linear in the table.  See :func:`_forth_ordered` for the
    stack discipline that keeps it balanced.

    A subtree whose rows all agree answers in place -- the node pushes the
    result byte instead of dispatching, and its whole subtree goes
    unemitted.  That costs nothing to arrange because Forþ keys its scope
    table by the number pushed before ``{`` and looks it up with a default,
    so a gap in the numbering is a scope that never exists; the step to the
    next emitted node simply spans it.  The reads sit outside the tree, so
    a folded program consumes its input exactly as an unfolded one does.

    ``;`` pops the stack, so the tree naturally tests the last input first.
    The generator keeps that order instead of enumerating reachable stack
    arrangements.
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

    Returns the arrangement (bottom to top, by input index) mapped to the
    program producing it; an absent arrangement is one the ops cannot reach.

    **The reachable set is a product, not a search.**  A read leaves its bit
    on top, and the only choice that outlasts the next read is how far that
    bit sinks -- 0, 1 or 2 places, since ``v`` and ``c`` reach no deeper.
    Composing one choice per read therefore enumerates every arrangement,
    ``2 * 3**(n - 2)`` of them, which a test pins.

    **Interleaving the sinks with the reads is what makes this worth doing.**
    Rotating only after all ``n`` reads would permute just the last three
    bits -- 6 arrangements at every width, which collapses the saving to
    2.4% at n == 4 and nothing at n == 5.  Sinking each bit as it arrives,
    before later reads bury it, reaches 18 at n == 4 and 54 at n == 5.

    A breadth-first search over (arrangement, reads done) finds op strings
    shorter on some arrangements, because they compose across reads -- a
    late ``c`` can do work several per-read ``v``s would each repeat.  It is
    not used: the generator retains its natural input order.
    """
    return stack_programs(n, _FORTH_SINKS, _FORTH_READ)


def _forth_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Forþ program; see :func:`forth`.

    ``truth_table`` is already permuted, so the tree is a plain contiguous
    most-significant-first walk and every row index here is self-consistent.
    ``perm`` surfaces only in the stack arrangement the reads must produce:
    the tree pops its test bit, so level ``k`` needs ``perm[k]`` on top and
    the stack bottom-to-top is ``perm`` reversed.

    Returns ``""`` when the ops cannot reach that arrangement, which is a
    signal to try another order rather than a failure.

    **The stack is balanced by construction, and has to be.**  An
    empty-stack pop is fatal in Forþ -- it halts the program rather than
    aborting a scope -- and the definition counter is left sitting under
    the bits, so the tree must never pop past them.  It does not: each
    dispatch consumes exactly one bit and one index and produces one index,
    so a walk to depth ``k`` has consumed ``k`` bits and holds one index,
    and the leaf pushes the answer byte above it.  The counter and the
    leaf's index are the only residue, both below the byte ``.`` prints.
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

    def rows_under(m: int) -> list[int]:
        """Return the table rows the subtree rooted at heap index ``m`` covers.

        The table is permuted, so the tree splits it most-significant-first
        and a node covers a contiguous run -- the leaf at heap index ``m``
        is row ``m - last_internal - 1``.
        """
        if m > last_internal:
            return [m - last_internal - 1]
        return rows_under(2 * m + 1) + rows_under(2 * m + 2)

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
            rows = rows_under(m)
            if len({truth_table[row] for row in rows}) == 1:
                # Every row under this node agrees, so the bits it would
                # branch on cannot change the answer: answer here and drop
                # the whole subtree.  The inputs are read up front, outside
                # the tree, so a folded program still consumes its input
                # exactly as an unfolded one does.
                body = _forth_const(_ASCII_ZERO + int(truth_table[rows[0]]))
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
    """Build a Modulous program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Modulous reads the inputs onto the stack with ``[INP INT]`` (top is the
    last input), then a decision tree branches on the top with
    ``[JMP F n IF 0/1]``, popping each checked bit. Each leaf pushes the
    result with ``[PSH INT]`` and prints it.
    """
    n = _validate_truth_table(truth_table)

    def build(rows: list[int], k: int) -> str:
        if len({truth_table[row] for row in rows}) == 1:
            return f"[PSH INT {truth_table[rows[0]]}][PRT INT][END]"
        g0 = [r for r in rows if ((r >> (n - k)) & 1) == 0]
        g1 = [r for r in rows if ((r >> (n - k)) & 1) == 1]
        sub0 = build(g0, k - 1)
        sub1 = build(g1, k - 1)
        d = 2 + sub0.count("[")
        return f"[JMP F 2 IF 0][JMP F {d} IF 1][POP]{sub0}[POP]{sub1}"

    return "[INP INT]" * n + build(list(range(2**n)), n)


def _bfstack_encoder(n: int) -> str:
    """BFStack code turning the n inputs into the number ``1 + sum(bit*2^k)``.

    Each input is read with ``,`` and normalized to 0/1 with 48 ``-``s; if it
    is one, ``[<+w>]`` adds its weight ``w`` to the accumulator below it.
    The ``+1`` offset keeps the result nonzero so the decoder's outer ``[``
    always runs (a ``0`` result would be ambiguous with a skipped loop).
    """
    prog = ">>+"  # result cell (0) below the accumulator (1)
    for k in range(n):
        weight = 2 ** (n - 1 - k)
        prog += "," + "-" * _ASCII_ZERO + "[" + "<" + "+" * weight + ">" + "]" + "<"
    return prog


def _bfstack_decoder(truth_table: str) -> str:
    """BFStack code mapping the encoded number to the table's result.

    The output is 1 for every input except the rows where the table is 0.
    Each such row maps to a distinct value of the ``+1``-offset number, so the
    decoder tests them by cumulative subtraction: ``[`` opens a ``while`` that
    only reaches the inner ``[<+>]`` (setting the result to 1) when the number
    survives every subtraction; hitting a zero row's value subtracts to 0 and
    skips the ``[<+>]`` instead, leaving the result 0.
    """
    zeros = [k + 1 for k, ch in enumerate(truth_table) if ch == "0"]
    if not zeros:
        return "[<+>]"  # always 1
    prog = "["
    prev = 0
    for z in zeros:
        prog += "-" * (z - prev) + "["
        prev = z
    prog += "[<+>]"
    prog += "]" * (len(zeros) + 1)
    return prog


def bfstack(truth_table: str) -> str:
    """Build a BFStack program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BFStack is a pure stack machine, so the generator avoids branching
    entirely: it encodes the n inputs as the number ``1 + sum(bit*2^k)``
    (each ``,`` reads and normalizes a bit, ``[<+w>]`` adds its weight), then
    decodes it with nested ``[`` loops that only set the result to 1 when the
    number is not one of the table's zero rows.
    """
    n = _validate_truth_table(truth_table)
    return (
        _bfstack_encoder(n)
        + _bfstack_decoder(truth_table)
        + "<"
        + "+" * _ASCII_ZERO
        + "."
    )


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Unsquare's ``>``/``<`` loop runs while the accumulator is neither 0 nor 1,
    so a 0/1 bit is turned into a loop condition by ``x`` (0 stays 0, 1
    becomes 2) and its negation by a stack-clean flip ``x->IA<`` (``0`` swaps
    to 1, ``1`` to 0).  Each input is read and reduced to 0/1 by ``>-<``
    (subtracting 2 until parity) and pushed; the decision tree then pops bits
    from the stack top and branches.  A branch that runs ends with ``IA``
    (leaving acc = 1 so the sibling's ``FLIP x > <`` guard skips), and each
    leaf pushes ``48 + entry`` and leaves acc = 0, so the final ``o`` prints
    exactly the matching row's entry.

    **The tree splits on its inputs in whichever order emits the shortest
    program.**  ``A`` pops, so the *natural* order tests the last input at
    the root -- Unsquare's tree is stack-ordered, not input-ordered, exactly
    as Forþ's is.

    This generator was long excluded from reordering on the reading that
    ``S`` swaps only the top two and there is one accumulator, so nothing
    rotates to depth.  That reads the ops singly.  Together they rotate,
    because **the accumulator is the second place to hold a bit**: ``A``
    pops the top into it, ``S`` swaps the two now exposed, and ``P`` pushes
    it back, sinking a bit two places (:data:`_UNSQUARE_SINKS`).

    At each read the generator greedily chooses whether to sink the new bit
    zero, one, or two places.  It prices those three reachable continuations
    with the exact tree-size model, so it builds one final program rather than
    enumerating ``2 * 3**(n-2)`` complete arrangements.

    The pricing is incremental (:class:`_UnsquarePricer`): the tree tests
    the still-natural inputs above the arranged ones, and sinking the new
    input ``s`` places re-tests only the top ``s + 1`` levels of each
    cofactor tree, so a read costs ``O(T / 2**k)`` and the order ``O(T)``
    in all.  Pricing every candidate from scratch was ``O(nT)`` each.
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


@cache
def _unsquare_stack_programs(n: int) -> dict[tuple[int, ...], str]:
    """Read-and-sink program for each reachable stack arrangement.

    Returns the arrangement (bottom to top, by input index) mapped to the
    program producing it; an absent arrangement is one the ops cannot reach.

    **The reachable set is a product, not a search.**  A read leaves its bit
    on top, and the only choice that outlasts the next read is how far that
    bit sinks -- 0, 1 or 2 places, since ``S`` and the one accumulator reach
    no deeper.  Composing one choice per read enumerates every arrangement,
    ``2 * 3**(n - 2)`` of them, which a test pins.  Forþ's stack has the same
    count for the same reason, reached through different ops.

    Forþ enumerates for the same reason and records a breadth-first search as
    the rejected alternative: there the search *does* find shorter op strings
    on some arrangements, because a late ``c`` composes across reads, and it
    is dropped as a trade -- 1-2 characters that mostly do not survive to the
    output, against code a reader can follow.  Here there is no trade.  A
    search over (arrangement, reads done) finds the *same* set with the
    *same* shortest string at every width through n == 7, because these sinks
    do not compose across reads at all, so the enumeration is both the
    simpler code and the optimal one.
    """
    return stack_programs(n, _UNSQUARE_SINKS, _UNSQUARE_READ)


class _UnsquarePricer:
    """Exact tree sizes for the greedy's candidates, one read at a time.

    The tree tests the natural (not yet read) inputs first, top-down from
    input ``n - 1`` to the one just read, and the arranged inputs below
    them, the stack's top first.  A node is a row index with the inputs
    still free below it zeroed; ``levels[d]`` holds, for every node at
    depth ``d`` of the arranged part, its constant value (``-1`` when
    mixed) and its cost -- 29 for a constant subtree, 17 plus the halves
    otherwise; the tests keep that model spelled recursively as the oracle.

    Sinking the new input ``s`` places puts it under ``s`` of the old top
    inputs, so the new tree's levels from ``s + 1`` down are the old
    levels from ``s`` down, node for node; only the top ``s + 1`` levels
    are re-merged, ``O(T / 2**k)`` at read ``k``, and the natural part
    above is re-merged from the new top, ``O(T / 2**k)`` again.
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

    ``truth_table`` is in the permuted frame, so bit ``k`` of a row index is
    the input tested at level ``k`` and the tree needs no reference to the
    order that produced it -- the stack prefix has already put the bits where
    the pops will find them.
    """
    flip = "x->IA<"

    def leaf(row: int) -> str:
        value = _ASCII_ZERO + int(truth_table[row])
        return ("IA" if value == _ASCII_ONE else "OA") + "+" * 24 + "P" + "OA"

    def build(rows: list[int], k: int) -> str:
        if len({truth_table[row] for row in rows}) == 1:
            return leaf(rows[0])
        g1 = [row for row in rows if ((row >> k) & 1) == 1]
        g0 = [row for row in rows if ((row >> k) & 1) == 0]
        return f"Ax>{build(g1, k + 1)}IA<{flip}x>{build(g0, k + 1)}OA<"

    return build(list(range(2**n)), 0) + "o"
