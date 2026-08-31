"""Boolean-function generator for SLOW ACV MAMMALIAN.

The language reads a byte with ``ACCEPT``, which appends ``byte ^ acc`` to
array 0 *whatever the pointer holds*, so nothing needs routing: the pointer
stays on array 0 for the whole program and the tree lives in code space,
built out of the one conditional the language has:

``ACCEPT DIGEST LEAPFROG``
    ``ACCEPT`` appends the bit (entering with ``acc % 256 == 48``, the digit
    ``'0'``/``'1'`` normalizes to a clean ``0``/``1``), ``DIGEST`` folds the
    array sum into the accumulator, and ``LEAPFROG`` jumps exactly when the
    array's last element -- the bit just read -- is nonzero.  So a 0 falls
    through to the next token and a 1 jumps: one node of a binary decision
    tree.

Every landing point is *computed*, never measured.  Bits are never popped
off the array on the branch that matters, so on any path the machine state
is known while generating, and the whole node is a closed form:

``SEED*wrap EXCRETE SEED*j1 DIGEST SEED*j2 DIGEST ACCEPT DIGEST LEAPFROG``
    ``wrap = (256 - head) % 256`` puts the head at 0 so a later ``SEED`` run
    cannot drop the sum by 256 partway through.  ``EXCRETE`` appends
    ``acc % 256`` and *clears* the accumulator, which is what makes the rest
    exact: the following ``DIGEST`` leaves ``acc`` equal to the sum rather
    than XORed against an unknown.  Writing ``S1`` for the sum after the
    ``j1`` run, ``j2 = ((S1 ^ 48) - S1) % 256`` forces the second ``DIGEST``
    to exit with ``acc = S1 ^ (S1 + j2)``, whose low byte is exactly 48 --
    the clean digit ``ACCEPT`` needs.

The high bytes of that accumulator are the aiming knob.  ``ACCEPT`` only
reads ``acc`` modulo 256, so ``acc = 48 + 256*H`` feeds the same clean digit
whatever ``H`` is, while ``H`` survives into the closing ``DIGEST`` and moves
the jump target in ~256-token steps *without touching the array*.  Sweeping
``j1`` over its 256 values enumerates the ``H`` band arithmetically -- no
program is ever run to find out where a jump goes.

Two identities make the tree compose.  A node's 0-branch exits with ``acc``
equal to the array sum exactly (``opening ^ second`` with the bit 0
appended), which is the same normal form the node itself starts from, and
the leaf that follows therefore needs no ``SEED``s at all.  So a subtree's
shape does not depend on how its parent aimed, only on how much ballast it
inherits.

Ballast is the other half.  A 0-subtree inherits its parent's array, and if
the sum could only grow, a child would convert every token its parent
stashed into padding of its own and the two would lock together one for
one.  ``CONSUME`` breaks the lock: the 0-arm sheds the stashed bytes back
off before its subtree builds, so the child starts from a small array
whatever the parent had to do to reach it.

What is left is assembler-style branch relaxation, not a search: sizes
depend on offsets and offsets on sizes, so the emitter sizes the 0-arm
once, picks the landing arithmetically, commits, and rechecks.  The tree is
uniform depth ``n``: constant tables are not folded, because the reads are
the interface and every table has to consume all ``n`` inputs.
"""

import itertools

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["slow_acv_mammalian_boolean"]

# The byte a stash chunk appends.  It is what raises the sum, and the sum is
# what puts a distant token index within a jump's reach, so the chunk buys
# the most reach per token by appending the largest byte there is.
_STASH_BYTE = 255

# Stashed bytes a shed run leaves in place.  ``CONSUME`` pops the *middle*
# element, so the array has to keep the head plus one element for the next
# pop to have something to take.
_SHED_KEEP = 2

# Candidates tried past the one the sizing pass picked.  The 0-arm's length
# is re-derived for whichever candidate is committed, and that length can
# differ from the sizing estimate, so the emitter walks a few neighbours.
# Exceeding this means the estimate and the rebuild disagree by more than
# the band is wide, which is a bug in the formulas rather than a table that
# needs more effort.
_MAX_RELAXATIONS = 8

# Chunks the stash loop looks back over when checking it is still closing
# the placement gap.  One step is not enough: the gap sawtooths up a few
# tokens on single iterations, and the *first* chunk always spikes it,
# since the layout lands before the reach it buys.  Over two, measured
# across every node of every table through ``n == 3`` (172452 nodes), the
# gap fell by at least 248 tokens every time with no exceptions.
_WINDOW = 2

# An upper bound on what one leaf's worth of the tree can cost, used only
# to reject a ``base`` no emission could have produced.  This is *input
# validation*, not part of the termination argument above: ``base`` is a
# partial sum of the lengths already emitted, so it cannot exceed the
# finished program, and a depth-``n`` tree has ``2**n`` leaves.  Measured
# per-leaf cost is 377 at ``n == 1``, 492 at ``n == 2`` and 565 at
# ``n == 3``, and a sampled ``n == 4`` came to 601, so this leaves room for
# the slow growth while still rejecting a nonsense base at once rather than
# after tens of thousands of chunks that cannot help.
_TOKENS_PER_LEAF = 1024

# ``DIGEST PRONOUNCE EXCRETE LEAPFROG``: the fixed tail every leaf ends with,
# which :func:`_zero_arm_length` has to account for without building one.
_LEAF_TAIL = 4


def _seeded(array: list[int], count: int) -> list[int]:
    """``array`` after ``count`` ``SEED``s, which only move the head."""
    out = list(array)
    out[0] = (out[0] + count) % 256
    return out


def _stash_chunk(array: list[int], acc: int) -> tuple[list[str], list[int], int]:
    """``SEED*k DIGEST EXCRETE``, appending exactly ``_STASH_BYTE``.

    ``SEED`` advances the sum by one per token, and a head wrap drops it by
    256, so the sum's *low byte* advances by exactly one either way.  Only
    the low byte is spent -- ``EXCRETE`` appends ``acc % 256`` -- so the
    count solves in one step instead of a scan.
    """
    count = (((acc % 256) ^ _STASH_BYTE) - sum(array)) % 256
    return (
        [*["SEED"] * count, "DIGEST", "EXCRETE"],
        [*_seeded(array, count), _STASH_BYTE],
        0,
    )


def _shed(array: list[int], acc: int) -> tuple[list[str], list[int], int]:
    """``CONSUME``s dropping the stashed ballast back off the array.

    ``CONSUME`` pops the middle element *into* the accumulator, clobbering
    it rather than XORing, and the node that follows opens with ``EXCRETE``
    -- which appends ``acc % 256`` straight back.  So the last pop rides
    back aboard and a lone ``CONSUME`` sheds nothing; a run sheds every
    value it pops but the last.
    """
    out, value, tokens = list(array), acc, []
    while len(out) > _SHED_KEEP + 1:
        value = out.pop((len(out) - 1) // 2)
        tokens.append("CONSUME")
    return tokens, out, value


_Node = tuple[list[str], tuple[list[int], int], tuple[list[int], int], int]


def _candidates(array: list[int], acc: int) -> list[_Node]:
    """Every read node this state admits, with where each one's jump lands.

    One entry per ``j1``: the tokens, the state the 0-branch falls through
    with, the state the 1-branch jumps with, and the index the jump resumes
    at.  All four are arithmetic in the sum -- nothing here runs a program.
    """
    wrap = (256 - array[0]) % 256
    opened = [*_seeded(array, wrap), acc % 256]
    start = sum(opened)
    found: list[_Node] = []
    for j1 in range(256):
        first = start + j1
        j2 = ((first ^ _ASCII_ZERO) - first) % 256
        # The head sits at ``j1 + j2`` after both runs; letting that pass 255
        # would wrap it and drop the sum out from under the arithmetic.
        if j1 + j2 > 255:
            continue
        second = first + j2
        # ``ACCEPT`` reads the accumulator modulo 256 and wants a clean
        # digit, and ``j2`` is chosen to deliver one: it is defined so that
        # ``second`` is congruent to ``first ^ _ASCII_ZERO`` mod 256, and XOR
        # is bitwise, so ``opening % 256`` is ``_ASCII_ZERO`` for every
        # ``first``.  The high bytes are free, and are exactly the aiming
        # knob.
        opening = first ^ second
        loaded = _seeded(opened, j1 + j2)
        tokens = [
            *["SEED"] * wrap,
            "EXCRETE",
            *["SEED"] * j1,
            "DIGEST",
            *["SEED"] * j2,
            "DIGEST",
            "ACCEPT",
            "DIGEST",
            "LEAPFROG",
        ]
        # ``LEAPFROG`` sets the cursor to ``acc - head - 1`` and the step
        # then advances it, so the token that runs next is one past that.
        landing = (opening ^ (second + 1)) - (j1 + j2) % 256
        found.append(
            (
                tokens,
                ([*loaded, 0], opening ^ second),
                ([*loaded, 1], opening ^ (second + 1)),
                landing,
            )
        )
    found.sort(key=lambda entry: (entry[3], len(entry[0])))
    return found


def _leaf_seeds(array: list[int], acc: int, bit: int) -> int:
    """``SEED``s bringing the accumulator onto the digit's residue class.

    Only ``acc % 256`` is ever printed, so this is the same one-step solve
    the stash chunk uses rather than a scan over 256 counts.
    """
    return (((acc % 256) ^ (_ASCII_ZERO + bit)) - sum(array)) % 256


def _leaf(array: list[int], acc: int, bit: int) -> list[str]:
    """Print the table entry, then halt.

    ``EXCRETE`` appends the printed byte (48 or 49, so nonzero: ``LEAPFROG``
    fires) and clears the accumulator, which makes the jump target
    ``0 - head - 1``.  That is negative, which the interpreter halts on.
    """
    count = _leaf_seeds(array, acc, bit)
    return [*["SEED"] * count, "DIGEST", "PRONOUNCE", "EXCRETE", "LEAPFROG"]


def _entry(table: str, row: str) -> int:
    """Read the table's value on the path ``row``."""
    return int(table[int(row, 2) if row else 0])


def _zero_arm(
    table: str,
    n: int,
    depth: int,
    row: str,
    state: tuple[list[int], int],
    at: int,
) -> list[str]:
    """Shed the inherited ballast, then build the 0-branch's subtree."""
    tokens, array, acc = _shed(*state)
    return [
        *tokens,
        *_subtree(table, n, depth + 1, f"{row}0", array, acc, at + len(tokens)),
    ]


def _zero_arm_length(table: str, row: str, state: tuple[list[int], int]) -> int:
    """Measure :func:`_zero_arm` without building it.

    Only correct one level above the leaves, where the arm is a shed run and
    a leaf and both are closed forms.  That is half the tree's nodes, and
    knowing the length exactly is what lets those nodes take the first
    candidate that fits instead of rebuilding to find out.
    """
    tokens, array, acc = _shed(*state)
    return len(tokens) + _leaf_seeds(array, acc, _entry(table, f"{row}0")) + _LEAF_TAIL


def _emit(
    table: str,
    n: int,
    depth: int,
    row: str,
    prefix: list[str],
    node: _Node,
    base: int,
    zero: list[str],
) -> list[str]:
    """Lay a committed node out: node, 0-arm, dead padding, 1-arm.

    The padding lands after the 0-arm's halting leaf, so it never executes;
    it only pushes the 1-subtree out to where the jump already goes.
    """
    tokens, _, taken, landing = node
    start = base + len(prefix) + len(tokens)
    one = _subtree(table, n, depth + 1, f"{row}1", *taken, landing)
    pad = landing - start - len(zero)
    return [*prefix, *tokens, *zero, *["SEED"] * pad, *one]


def _subtree(
    table: str, n: int, depth: int, row: str, array: list[int], acc: int, base: int
) -> list[str]:
    """Build the subtree rooted here, knowing it starts at token ``base``."""
    if depth == n:
        return _leaf(array, acc, _entry(table, row))

    prefix: list[str] = []
    cursor, value = list(array), acc
    # The first chunk's layout lands before the reach it buys, so the gap
    # spikes once at the start; the descent below is checked over what
    # follows that prologue rather than over the spike.
    window: list[int] = []
    # ``base`` is a partial sum of what has already been emitted, so it
    # cannot outrun the finished program.  One past that describes a tree no
    # emission could have produced, and its gap is too large for any run of
    # chunks to close -- worth saying at once rather than after tens of
    # thousands of them.  This is validation rather than termination: what
    # ends the loop is placing, or the convergence check below.
    if base > _TOKENS_PER_LEAF * 2**n:
        raise ValueError(
            f"the subtree at depth {depth}, row {row!r} starts at token {base}, "
            f"past anything a {n}-input tree could emit"
        )
    for spent in itertools.count():
        candidates = _candidates(cursor, value)
        gap = _placement_gap(table, n, depth, row, prefix, candidates, base)
        if spent:
            window.append(gap)

        # A chunk buys ~255 tokens of reach against the layout it adds, but
        # the layout outruns the reach on the *first* chunk, and thereafter
        # sawtooths up a few tokens on single steps.  So progress is checked
        # over a two-step window and only once the first chunk is past:
        # measured that way the gap fell by at least 248 tokens every window,
        # with no exceptions.  A window that fails to close is the
        # parent/child lock this construction exists to break -- the 0-arm's
        # shed no longer decoupling the child from inherited ballast -- which
        # is a bug in the formulas, not a table that needs a bigger budget.
        if len(window) > _WINDOW + 1:
            window.pop(0)
        if len(window) == _WINDOW + 1 and window[-1] >= window[0]:
            raise ValueError(
                f"the stash loop stopped converging at depth {depth}, row {row!r}: "
                f"the placement gap went {window[0]} -> {window[-1]} over "
                f"{_WINDOW} chunks"
            )

        placed = _place(table, n, depth, row, prefix, candidates, base)
        if placed is not None:
            return placed
        chunk, cursor, value = _stash_chunk(cursor, value)
        prefix = [*prefix, *chunk]
    raise AssertionError(  # pragma: no cover - the loop only leaves by return
        "the stash loop fell out of an endless counter"
    )


def _place(
    table: str,
    n: int,
    depth: int,
    row: str,
    prefix: list[str],
    candidates: list[_Node],
    base: int,
) -> list[str] | None:
    """Lay this node out, if any candidate's landing clears its 0-arm."""
    if depth + 1 == n:
        return _place_above_leaves(table, n, depth, row, prefix, candidates, base)
    return _place_inner(table, n, depth, row, prefix, candidates, base)


def _placement_gap(
    table: str,
    n: int,
    depth: int,
    row: str,
    prefix: list[str],
    candidates: list[_Node],
    base: int,
) -> int:
    """How far the furthest landing still falls short of clearing the 0-arm.

    This is the quantity placement actually turns on, so it is the one the
    loop can descend.  The obvious cheaper proxy -- the shortfall against
    the *node* alone, leaving the arm out -- does not work: its zero region
    does not force a placement, and over the tables through ``n == 3`` there
    were 13512 iterations where it had gone negative and placement still
    refused.
    """
    reach = base + len(prefix) + len(candidates[0][0])
    arm = (
        _zero_arm_length(table, row, candidates[0][1])
        if depth + 1 == n
        else len(_zero_arm(table, n, depth, row, candidates[0][1], reach))
    )
    return reach + arm - candidates[-1][3]


def _place_above_leaves(
    table: str,
    n: int,
    depth: int,
    row: str,
    prefix: list[str],
    candidates: list[_Node],
    base: int,
) -> list[str] | None:
    """Place a node whose 0-arm is a shed run and a leaf.

    Both are closed forms, so the arm's length is known before it is built
    and the first candidate that clears it is the one to take.
    """
    for node in candidates:
        tokens, fell, _, landing = node
        start = base + len(prefix) + len(tokens)
        if landing < start + _zero_arm_length(table, row, fell):
            continue
        zero = _zero_arm(table, n, depth, row, fell, start)
        return _emit(table, n, depth, row, prefix, node, base, zero)
    return None


def _place_inner(
    table: str,
    n: int,
    depth: int,
    row: str,
    prefix: list[str],
    candidates: list[_Node],
    base: int,
) -> list[str] | None:
    """Place a node whose 0-arm has to be built to be measured.

    Sizing it against one candidate is enough to pick the landing, but the
    arm's length shifts a little between candidates, so the committed one is
    rebuilt and a few neighbours are tried when the two disagree.
    """
    sized, _, _, _ = candidates[0]
    estimate = len(
        _zero_arm(
            table, n, depth, row, candidates[0][1], base + len(prefix) + len(sized)
        )
    )
    reach = base + len(prefix)
    if candidates[-1][3] < reach + len(sized) + estimate:
        return None

    first = next(
        (
            index
            for index, (tokens, _, _, landing) in enumerate(candidates)
            if landing >= reach + len(tokens) + estimate
        ),
        0,
    )
    for node in candidates[first : first + _MAX_RELAXATIONS]:
        tokens, fell, _, landing = node
        start = reach + len(tokens)
        if landing < start:
            continue
        zero = _zero_arm(table, n, depth, row, fell, start)
        if landing < start + len(zero):
            continue
        return _emit(table, n, depth, row, prefix, node, base, zero)
    return None


def slow_acv_mammalian_boolean(truth_table: str) -> str:
    """Build a SLOW ACV MAMMALIAN program evaluating ``truth_table``.

    The program reads ``n`` digits with ``ACCEPT`` and prints the table entry
    for the combination it was given.  It is a decision tree of uniform depth
    ``n``, so a constant table still reads all ``n`` inputs.
    """
    n = _validate_truth_table(truth_table)
    if n == 0:
        return " ".join(_leaf([0], 0, int(truth_table)))
    return " ".join(_subtree(truth_table, n, 0, "", [0], 0, 0))
