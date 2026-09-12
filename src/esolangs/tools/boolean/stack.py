"""Boolean-function generators for stack-based languages."""

from functools import cache
from itertools import product

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _ORDER_SEARCH_MAX,
    _validate_truth_table,
    essential_inputs,
    minterm_literals,
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

#: Digit letters a variable key may use, in slot order.
#:
#: A key is written ``F<letter>F``, where the letter is the digit and the
#: ``F``s delimit int mode -- so the letter ``F`` cannot be a digit, and
#: ``chr(key // 10 + 64)`` walked straight into it.  Slot 5's key of 60
#: encoded as ``FFF``: three delimiters and no number.  The framing then
#: collapsed for the rest of the program, and the *next* slot's letter was
#: then executed as a command.  Restoring the old alphabet reproduces both
#: deaths: six essential inputs raised ``ProgramError: Grapheme produced no
#: answer this could read``, and seven raised ``HaltError: G needs a string
#: or a function``.
#:
#: ``I`` is skipped for a second, quieter collision.  It is 90, the key the
#: normalizing constant already lives in, so with only ``F`` removed slot 7
#: stores its input bit over the 65.  That one does not raise -- eight
#: essential inputs still come out right, because slot 7 is read last and
#: nothing reads the constant afterwards, and it is *nine* that returns a
#: wrong table.  A wrong answer that arrives quietly is the worse of the
#: two, and it is the reason this list is filtered rather than shortened.
#:
#: Both walls stood at *essential* inputs, not arity: a table of any size
#: that reduces to five or fewer inputs always worked, which is why the
#: build sweep -- which never runs what it builds -- saw nothing.
_GRAPHEME_KEY_LETTERS = [
    letter
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if letter not in {"F", chr(_GRAPHEME_CONST_KEY // 10 + 64)}
]


def _grapheme_slot_key(slot: int) -> int:
    """Return the variable key holding input ``slot``."""
    if slot >= len(_GRAPHEME_KEY_LETTERS):  # pragma: no cover - see below
        # Twenty-four usable keys against a table that would need 2**24
        # rows to reach them; unreachable, and refused rather than aliased.
        raise GeneratorCapError(
            f"Grapheme has {len(_GRAPHEME_KEY_LETTERS)} variable keys, "
            f"and slot {slot} needs one past them"
        )
    return (ord(_GRAPHEME_KEY_LETTERS[slot]) - 64) * 10


def _grapheme_push_key(key: int) -> str:
    """Grapheme code pushing the integer variable key ``key`` (a multiple of 10)."""
    return "F" + chr(key // 10 + 64) + "F"


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
    table is evaluated as a sum of minterms: the result is ``1`` minus the
    sum of the ``0``-rows' minterms, or the sum of the ``1``-rows' minterms,
    whichever comes out *shorter* (each minterm is the arithmetic AND, ``S``,
    of the bits or their complements ``1 - b``).  Since exactly one row's
    minterm is 1 for any input, the accumulator holds the table entry, which
    ``Y`` prints.  No control-flow jumps are needed — only ``A``/``B``/``S``
    arithmetic and ``T``.
    """
    n = _validate_truth_table(truth_table)

    # A table that ignores some of its inputs is a smaller table, and every
    # minterm here spends one factor per input, so dropping an input shortens
    # each of the (now fewer) minterms as well.  The reads stay -- they are
    # the interface -- but an ignored one costs a *single* character: ``W``
    # pushes the line it read and nothing pops it, since every operator here
    # pops what it consumes and ``Y`` prints the top of the stack, so a value
    # left below the accumulator is unreachable rather than merely unused.
    # That makes it cheaper than taglate's rotate-and-drop, which has a
    # queue's positional arithmetic to keep undisturbed.
    head, table, width = _grapheme_head(truth_table, n)

    # Evaluate over one side of the table and fold its minterms.  Both sides
    # are built and the shorter kept, because the row *count* the sparser
    # rule went by is only a proxy for length and gets it wrong two ways.
    #
    # The sides do not cost the same per row: a negated literal spends eight
    # characters more than a plain one, so a row's cost falls with its
    # popcount (47 characters at row 0 against 23 at row 7, width 3) and two
    # sides with equal counts can differ by a lot.  Nor do they start the
    # same: the zero side seeds the accumulator with ``_grapheme_push1()``
    # (7 characters) against the one side's ``_grapheme_push0()`` (3), which
    # a count comparison cannot see at all -- and the old rule's ``<=`` gave
    # every tie to the expensive seed, so a balanced table always lost.
    #
    # Measured against the count rule: 45 of 256 tables at n == 3 came out
    # longer, by up to 52 characters, and 7654 of 65536 at n == 4 by up to
    # 100.  Building both is cheap here because the program *is* the string
    # -- there is no assembly step -- and the two sides together spend one
    # minterm per row of the table.  The comparison is strict, so a table
    # the other side does not shorten emits exactly what it emitted before.
    zero_side = _grapheme_side(table, width, head, zero_rows=True)
    one_side = _grapheme_side(table, width, head, zero_rows=False)
    return one_side if len(one_side) < len(zero_side) else zero_side


def _grapheme_head(truth_table: str, n: int) -> tuple[str, str, int]:
    """Emit the reads, and return them with the reduced table and its width.

    Shared by the two side builders below, which differ only in what they
    fold onto the accumulator -- the reads are the interface and are the
    same either way.
    """
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    # Slot ``s`` holds original input ``used[s]``; the minterm body is
    # written over the reduced table's slots, so it never names a dropped one.
    slot_of = {i: s for s, i in enumerate(used)}

    prog = [
        _grapheme_push65() + _grapheme_push_key(_GRAPHEME_CONST_KEY) + "C"
    ]  # the normalization constant
    for i in range(n):
        if i not in slot_of:
            prog.append("W")  # read the ignored input and abandon it
            continue
        # W reads the bit; normalize to 0/1; store under key 10*(slot+1).
        prog.append(
            "W"
            + _grapheme_push_key(_GRAPHEME_CONST_KEY)
            + "D"
            + "B"
            + "T"
            + _grapheme_push_key(_grapheme_slot_key(slot_of[i]))
            + "C"
        )
    return "".join(prog), table, len(used)


def _grapheme_side(table: str, width: int, head: str, *, zero_rows: bool) -> str:
    """Fold one side of the table onto the accumulator.

    ``zero_rows`` sums the ``0``-rows' minterms and subtracts them from 1;
    otherwise the ``1``-rows' minterms are summed directly.  The seeds differ
    in length (7 characters against 3), which is half of why the row count
    the old rule compared is not the program's length.
    """
    rows = [r for r in range(2**width) if (table[r] == "0") == zero_rows]
    acc, op = (_grapheme_push1(), "B") if zero_rows else (_grapheme_push0(), "A")
    body = [acc]
    for row in rows:
        body.append(_grapheme_push1())  # start this minterm at 1
        for i, negated in minterm_literals(row, width):
            if negated:
                # factor = 1 - b_i
                body.append(
                    _grapheme_push1()
                    + _grapheme_push_key(_grapheme_slot_key(i))
                    + "D"
                    + "B"
                )
            else:
                # factor = b_i
                body.append(_grapheme_push_key(_grapheme_slot_key(i)) + "D")
            body.append("S")
        body.append(op)  # fold the minterm into the accumulator
    return head + "".join(body) + "Y"


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
    builds a decision tree out of functions:     ``{ scope }`` stores a scope in
    the function table, and an internal node dispatches with ``base + ;``,
    which pops the top bit and calls ``table[base + bit]``.  Each input is
    read and normalized to 0/1 with ``,68*-``, the root dispatches with
    ``1+;``, and a leaf pushes ``48 + result`` which the final ``.`` prints.
    The definition indices are left on the stack below the result; the
    ``{ }`` construct reads (but does not pop) the top index, and ``;`` pops
    it, so the stale indices never get in the way of the dispatch arithmetic.

    A subtree whose rows all agree answers in place -- the node pushes the
    result byte instead of dispatching, and its whole subtree goes
    unemitted.  That costs nothing to arrange because Forþ keys its scope
    table by the number pushed before ``{`` and looks it up with a default,
    so a gap in the numbering is a scope that never exists; no index has to
    move.  The reads sit outside the tree, so a folded program consumes its
    input exactly as an unfolded one does.

    **The tree splits on its inputs in whichever order emits the shortest
    program.**  ``;`` pops the stack, so the *natural* order tests the last
    input at the root -- Forþ's decision tree is stack-ordered, not
    input-ordered.  Other orders are reachable because the stack can be
    rearranged: ``v`` swaps the top two and ``c`` rotates the third to the
    top (``o`` reverses the whole stack and is unusable here, since the
    scope indices sit below the bits and would come with it).

    **The rotations are interleaved with the reads, not run after them.**
    ``v``/``c`` reach only the top three cells, so a preamble after all
    ``n`` reads can only permute the last three bits -- 6 arrangements at
    any width, which collapses the saving to 2.4% at n == 4 and nothing at
    n == 5.  Moving a bit *while it is still near the top*, before later
    reads bury it, reaches 18 of 24 arrangements at n == 4 and 54 of 120 at
    n == 5 for a median of 2-3 extra characters
    (:func:`_forth_stack_programs`).

    Every rotation costs characters, so an order pays for the folds it wins
    or loses to the natural one; the search measures rather than assumes.
    Each order is scored in closed form (:func:`_forth_order_length`) and
    only the winner is built.  Measured over all 256 tables at n == 3 the
    saving is 13.8% (112 improved), with 13.2% and 14.3% over samples at
    n == 4 and n == 5.
    """
    n = _validate_truth_table(truth_table)
    # ``;`` pops, so the tree tests the *last* input at the root: the order
    # this generator has always emitted is the reversal, not the identity.
    # It goes first and ties keep it, so a table no reorder helps emits
    # exactly what it emitted before.
    natural = tuple(reversed(range(n)))
    # Score the *reachable* arrangements rather than all ``n!`` orders --
    # the keys of ``_forth_stack_programs``, ``2 * 3**(n - 2)`` of them,
    # checked equal through ``n == 6`` to the orders ``_forth_ordered``
    # accepts -- and build only the winner.  The contest that used to build
    # 13,122 full programs at n == 10 (61-68s) now builds one (0.2s),
    # byte-identical at every n <= 10, both benchmark shapes.  An
    # arrangement is the input order reversed.
    bits = int(truth_table[::-1], 2)  # bit ``r`` mirrors ``truth_table[r]``
    programs = _forth_stack_programs(n)
    best_perm = natural
    best_len = _forth_order_length(
        _forth_permuted_bits(bits, natural, n), n, len(programs[tuple(range(n))])
    )
    for arrangement, reads in programs.items():
        perm = tuple(reversed(arrangement))
        if perm == natural:
            continue
        length = _forth_order_length(_forth_permuted_bits(bits, perm, n), n, len(reads))
        if length < best_len:
            best_perm, best_len = perm, length
    return _forth_ordered(permute_truth_table(truth_table, best_perm), best_perm)


# The read that pushes one normalized input bit.
_FORTH_READ = ",68*-"


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
    not used: the difference is 1-2 characters on an intermediate string,
    and since :func:`forth` keeps the shortest program over every order, a
    longer rotation usually loses to a different order instead.  Measured
    over the emitted programs the whole effect is +0.13% at n == 3 and
    +0.03% at n == 5, which does not pay for a search in a generator meant
    to be read.
    """
    return stack_programs(n, _FORTH_SINKS, _FORTH_READ)


#: Per internal depth, root children first: (subtree rows, stride mask over
#: the packed table, the saving shared by the whole level or ``None``, the
#: per-node savings).  A level's savings share one value whenever no heap
#: index in it or below it crosses a base-15 digit boundary.
_ForthLevels = tuple[tuple[int, int, int | None, tuple[int, ...]], ...]


def _forth_const_len(value: int) -> int:
    """``len(_forth_const(value))`` in closed form: 4 per digit, minus 3."""
    if value == 0:
        return 1
    digits = 0
    while value:
        digits += 1
        value //= 15
    return 4 * digits - 3


@cache
def _forth_metrics(n: int) -> tuple[int, int, _ForthLevels, tuple[int, ...]]:
    """Constants :func:`_forth_order_length` needs at arity ``n``.

    Returns ``(all_mask, full, levels, axis)``: the packed table's full
    mask, the no-fold program length short of the reads and root dispatch,
    the per-depth fold accounting (:data:`_ForthLevels`), and per row-index
    bit the mask of rows with that bit set (for the delta swaps).
    """
    size = 2**n
    last_internal = size - 2
    top = 2 ** (n + 1) - 1  # heap indices run 1 .. top - 1
    length = [_forth_const_len(m) for m in range(2 * top)]
    # No-fold cost of the subtree at heap index ``m``: a leaf emits
    # ``m { const }`` (the body is 5 characters for 48 and 49 alike, so no
    # cost depends on the table), an internal node ``m { 2m+1 +; }`` plus
    # both children.
    subtree = [0] * top
    for m in range(top - 1, 0, -1):
        if m > last_internal:
            subtree[m] = length[m] + 7
        else:
            subtree[m] = (
                length[m]
                + length[2 * m + 1]
                + 4
                + subtree[2 * m + 1]
                + subtree[2 * m + 2]
            )
    levels = []
    for d in range(1, n):
        rows = 2 ** (n - d)
        stride = sum(1 << (j * rows) for j in range(2**d))
        base = 2**d - 1
        # Folding node ``m`` trades its whole subtree for one answer node.
        saves = tuple(subtree[base + j] - (length[base + j] + 7) for j in range(2**d))
        scalar = saves[0] if all(v == saves[0] for v in saves) else None
        levels.append((rows, stride, scalar, saves))
    axis = tuple(sum(1 << r for r in range(size) if (r >> p) & 1) for p in range(n))
    return (1 << size) - 1, subtree[1] + subtree[2], tuple(levels), axis


def _forth_permuted_bits(bits: int, perm: tuple[int, ...], n: int) -> int:
    """:func:`permute_truth_table` on a table packed as bit ``r`` = row ``r``.

    Slot ``s`` of the permuted table varies with input ``perm[s]``, which on
    row-index bits moves axis ``p`` to ``n - 1 - perm[n - 1 - p]``; each
    transposition of that permutation's cycles is one delta swap on the
    packed table.  O(n) big-int ops per order against ``read_at``'s
    ``O(n * 2**n)`` Python loop, a fifth of the old runtime.
    """
    axis = _forth_metrics(n)[3]
    dest = [n - 1 - perm[n - 1 - p] for p in range(n)]
    seen = [False] * n
    for start in range(n):
        if seen[start] or dest[start] == start:
            seen[start] = True
            continue
        cycle = []
        p = start
        while not seen[p]:
            seen[p] = True
            cycle.append(p)
            p = dest[p]
        for i in range(len(cycle) - 1):
            a, b = cycle[i], cycle[i + 1]
            if a > b:
                a, b = b, a
            delta = (1 << b) - (1 << a)
            low = axis[a] & ~axis[b]
            moved = ((bits >> delta) ^ bits) & low
            bits ^= moved ^ (moved << delta)
    return bits


def _forth_order_length(bits: int, n: int, reads_len: int) -> int:
    """Length of ``_forth_ordered`` on the packed permuted table, unbuilt.

    The no-fold total plus the reads and root dispatch, minus what each
    *maximal* constant subtree saves.  Constancy is monotone -- a constant
    node's children are constant -- so maximal is exactly "constant with a
    non-constant parent", and the depth-1 nodes have no parent to check.
    Checked equal to ``len(_forth_ordered(...))`` for every arrangement
    over all 256 tables at n == 3 and structured/random tables through
    n == 6.
    """
    all_mask, full, levels, _ = _forth_metrics(n)
    # All-ones/all-zeros run ladders, doubling the run once per level; a
    # subtree is constant when either survives.  An empty level ends the
    # climb: a constant run of ``2 * rows`` needs constant runs of ``rows``.
    const_at: dict[int, int] = {}
    ones = bits
    zeros = bits ^ all_mask
    for rows, stride, _, _ in reversed(levels):
        half = rows >> 1
        ones &= ones >> half
        zeros &= zeros >> half
        const = (ones | zeros) & stride
        const_at[rows] = const
        if not const:
            break
    save = 0
    for depth, (rows, _stride, scalar, saves) in enumerate(levels, start=1):
        const = const_at.get(rows, 0)
        if const and depth > 1:
            parent = const_at.get(2 * rows, 0)
            const &= ~(parent | (parent << rows))
        if not const:
            continue
        if scalar is not None:
            save += scalar * const.bit_count()
            continue
        shift = n - depth
        while const:
            low = const & -const
            save += saves[(low.bit_length() - 1) >> shift]
            const ^= low
    return full + reads_len + 4 - save


def _forth_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Forþ program; see :func:`forth`.

    ``truth_table`` is already permuted, so the tree is a plain contiguous
    most-significant-first walk and every row index here is self-consistent.
    ``perm`` surfaces only in the stack arrangement the reads must produce:
    the tree pops its test bit, so level ``k`` needs ``perm[k]`` on top and
    the stack bottom-to-top is ``perm`` reversed.

    Returns ``""`` when the ops cannot reach that arrangement, which is a
    signal to try another order rather than a failure.
    """
    n = _validate_truth_table(truth_table)
    wanted = tuple(reversed(perm))
    reads = _forth_stack_programs(n).get(wanted)
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
                body = _forth_const(2 * m + 1) + "+;"
        else:  # leaf: push the result byte
            body = _forth_const(_ASCII_ZERO + int(truth_table[m - last_internal - 1]))
        prog.append(_forth_const(m) + "{" + body + "}")
    prog.append(reads)  # the reads, with this order's rotations woven in
    prog.append("1+;.")  # root dispatch, then print the result
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

    **The sinks are interleaved with the reads, not run after them.**  A bit
    stashed in the accumulator does not survive a read block -- the block's
    own ``A`` overwrites it -- so a bit has to be moved while still near the
    top, before later reads bury it.  Every sink costs characters, so an
    order pays for the folds it wins or loses to the natural one and the
    search measures rather than assumes.  Measured saving: 15.6% over all
    256 tables at n == 3 (112 improved, none grown), 18.0% and 13.8% over
    samples at n == 4 and n == 5.
    """
    n = _validate_truth_table(truth_table)
    # ``A`` pops, so the tree tests the *last* input at the root: the order
    # this generator has always emitted is the identity *arrangement* (no
    # sinks), which is the reversal as an input order.  It goes first and ties
    # keep it, so a table no reorder helps emits exactly what it emitted
    # before.
    arrangements = _unsquare_stack_programs(n)

    def candidate_from(arrangement: tuple[int, ...]) -> tuple[int, str, str]:
        """Price the program whose stack ends in ``arrangement``."""
        # The tree pops LIFO, so an arrangement tests its inputs in reverse.
        # ``permute_truth_table`` puts the input tested at level ``k`` in the
        # table's ``k``-th *most* significant bit, but this tree splits on
        # ``row >> k`` -- least significant first, because that is the order
        # the pops arrive in.  Passing the arrangement itself converts between
        # the two frames; without it a table is read against the wrong axis
        # and the program computes a different function.
        table = permute_truth_table(truth_table, arrangement)
        prefix = arrangements[arrangement]
        return _unsquare_cost(table, n, prefix), table, prefix

    # The natural order is the identity arrangement, which the product always
    # reaches (every sink can be zero), so this needs no reachability check.
    best: tuple[int, str, str] | None = None
    # Iterate the *reachable* arrangements rather than all ``n!`` orders:
    # only ``2 * 3**(n - 2)`` of them can be built, so this is the candidate
    # set rather than a filter over a much larger one.  (The unreachable
    # orders are exactly the ones ``candidate`` would return ``None`` for.)
    #
    # Still capped, because ``3**n`` builds of an ``O(2**n)`` program is the
    # same cost shape the shared helper caps for, just with a smaller base:
    # n == 10 is 18 seconds of a call that is milliseconds at n == 6.  Above
    # the cap only the natural order is emitted, which is what this generator
    # produced before reordering existed -- never worse, just unimproved.
    for arrangement in arrangements:
        if n > _ORDER_SEARCH_MAX and arrangement != tuple(range(n)):
            continue
        candidate = candidate_from(arrangement)
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:  # pragma: no cover - the identity arrangement is reachable
        raise RuntimeError("Unsquare's identity stack arrangement is missing")
    _, table, prefix = best
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


def _unsquare_cost(truth_table: str, n: int, prefix: str) -> int:
    """Return one Unsquare candidate's exact rendered length without emitting it."""
    _validate_truth_table(truth_table)

    def cost(rows: list[int], bit: int) -> int:
        if len({truth_table[row] for row in rows}) == 1:
            return 29
        ones = [row for row in rows if (row >> bit) & 1]
        zeros = [row for row in rows if not (row >> bit) & 1]
        return 17 + cost(ones, bit + 1) + cost(zeros, bit + 1)

    return len(prefix) + cost(list(range(2**n)), 0) + 1


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
