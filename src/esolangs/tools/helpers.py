"""Shared helpers for the boolean-function program generators.

The generators in this package build programs that read ``n`` boolean
inputs and print the result of a truth table; the helpers here are the
common input handling they all repeat.

A truth table's length determines its input count: a valid table has
``2**n`` entries, so ``n`` is recovered from the table alone and the
generators take no ``n`` parameter.
"""

import re
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

    A valid table has ``2**n`` binary entries, so ``n`` is recovered from
    the length (a power of two).

    A **one-entry** table is rejected.  It is a well-formed power of two
    (``2**0``), so it used to pass: forty-four generators built a program
    for it, twenty-four crashed with an ``IndexError`` reaching for an
    input that was not there, and sixteen more raised ``negative shift
    count`` -- a ``ValueError``, but not one that says what is wrong.  Only
    COD and 123 refused it deliberately.  A nullary table is a *constant*,
    not a boolean function of any input, and the generators exist to build
    programs that read their inputs and branch, so it is refused here once
    rather than crashed on sixty times.
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

    The arity rule above is the generators' public contract, but a
    generator that reduces a table to its essential inputs can legitimately
    reach a one-entry table on the way down: a constant table projects to
    exactly that, and the reduced table is then solved as a constant rather
    than refused.  Minifuck's ``_solve`` is the one caller -- its public
    entry still validates in full, so the relaxation never reaches an API.
    """
    # The alphabet is checked first because it is the more specific
    # complaint: ``01a`` is three characters, so a length-first order
    # answered it with "must have a power-of-two number of entries, got 3"
    # and never mentioned the ``a`` that was actually wrong.
    #
    # Spelled as a set difference rather than ``all(c in "01" ...)``: this
    # is a per-character check on every candidate build.
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

    A sum-of-minterms program costs one term per row it selects, so a table
    with more ones than zeros is cheaper evaluated complemented and
    inverted: every term saved is paid for once, by whatever the language
    spells ``1 - x`` as.

    Every generator in that family uses this, and each reads the *returned*
    table -- selecting its ``1`` rows, which are the original's ``0`` rows
    when it flipped.  What differs is only how the flag is spent, and it is
    often free: Collatz Multiverse's OR already ends on the complement it
    would have added, and Point Break's loop guard is ``1 - f`` for reasons
    of its own, so both simply drop a step instead of gaining one.

    **A constant table may need excluding, and that is the caller's.**  An
    all-ones table complements to no minterms at all, which is the shape an
    all-*zeros* table has -- fine where the sum feeds an inversion that
    turns 0 back into 1, and wrong where the empty case is special-cased
    into a different construction, as Circuit Diagram's single self-fed
    gate is.
    """
    if truth_table.count("1") > len(truth_table) // 2:
        return _complement(truth_table), True
    return truth_table, False


def minterm_literals(row: int, n: int) -> list[tuple[int, bool]]:
    """Return the literals whose product is 1 exactly on ``row``.

    One ``(input, negated)`` pair per input, in input order: ``negated`` is
    True where ``row`` has that input clear, so the minterm wants ``1 - b``
    rather than ``b``.  The table is indexed most significant first, which
    is what makes input ``i`` bit ``n - 1 - i`` of the row index.

    Every sum-of-minterms generator needs exactly this, and each used to
    spell it out: ``(k >> (n - 1 - i)) & 1``, once per generator, with the
    MSB-first convention re-derived each time.  What they do *with* a
    literal is genuinely per-language -- qoibl names a variable, rotfuck
    picks a guard cell, Circuit Diagram indexes a bus pair -- so this
    returns the selection as data and leaves the emitting alone.

    Only the *literals* are shared.  Which rows to enumerate is the
    caller's: :func:`grapheme` evaluates whichever of the one-rows and
    zero-rows is the shorter list, so this takes one row at a time rather
    than walking the table itself.
    """
    return [(i, not (row >> (n - 1 - i)) & 1) for i in range(n)]


SetBit = Callable[[int, int], str]

#: One ``(zero, one)`` pair per input, in name order: what a template's
#: slots are filled with.  Each pair is equal width, checked by
#: :func:`check_setters`, so the constant-width convention is a property
#: of the object rather than of every caller.
Setters = tuple[tuple[str, str], ...]

_SLOT = re.compile(r"\{X(\d+)\}")


def slot_count(template: str) -> int:
    """How many inputs a template's ``{Xi}`` slots name."""
    return len({int(index) for index in _SLOT.findall(template)})


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


def check_slots(template: str, n: int) -> None:
    """Refuse a template whose slots are not ``{X0}``..``{Xn-1}``, once, in order."""
    slots = [int(index) for index in _SLOT.findall(template)]
    if slots != list(range(n)):
        raise ValueError(
            f"template slots must be {{X0}}..{{X{n - 1}}} once each in order, "
            f"found {slots}"
        )


#: The character a public template spells its inputs with, unless a
#: language declares another: outside every embedding language's alphabet.
TEMPLATE_CHAR = "$"


def render(template: str, char: str, setters: Setters) -> str:
    """Return the public template: each ``{Xi}`` as a run of ``char``.

    The run is as long as input ``i``'s setters, so the template is the
    exact shape of every program it fills to, and consecutive inputs need
    no separator between their runs -- the widths say where one ends.
    """
    check_slots(template, len(setters))
    for i, (zero, _one) in enumerate(setters):
        template = template.replace("{X" + str(i) + "}", char * len(zero))
    return template


def runs(text: str, char: str, setters: Setters) -> list[tuple[int, int]]:
    """Return the ``[start, end)`` of each input's run in ``text``.

    Runs of ``char`` are consumed left to right in consecutive setter
    widths, and every occurrence of ``char`` must belong to one: a run of
    the wrong length, a run left over, or a ``char`` in the program text
    proper all refuse, since each means the template is not the shape its
    setters describe.
    """
    widths = [len(zero) for zero, _one in setters]
    spans: list[tuple[int, int]] = []
    position = 0
    for i, width in enumerate(widths):
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


def instantiate(template: str, bits: list[int], set_bit: SetBit | Setters) -> str:
    """Substitute each ``{Xi}`` placeholder.

    ``{Xi}`` becomes ``set_bit(i, bit)``, the language's code for setting
    input ``i`` to the bit; ``set_bit`` may also be the :data:`Setters`
    pairs themselves, indexed the same way.

    **A ``set_bit`` must return the same width for a 0 and a 1.**  This is the
    one place the generators deliberately give up shortness.  Spelling a zero
    as nothing at all (or as a shorter run than a one) is always tempting and
    always wrong: it makes the emitted program's *length* a function of its
    inputs, so the program leaks the very bits it is supposed to be evaluating.
    At ``n == 2`` an earlier Bio embedding ran to 236, 240, 244, and 248
    characters for the four instantiations -- the input recoverable from
    ``len(program)`` without reading a line of it.

    So pad the shorter side to equal width, and prefer padding with characters
    the language *executes* to a no-op over characters it merely ignores: the
    ignored kind is what a later cleanup pass strips, reintroducing the leak.
    :func:`~esolangs.tools.bio` (``0oz;``) and
    ``bfstack`` (a four-character run proved minimal by exhaustive search over
    ``<>@[]``) are the worked examples.

    There used to be a ``{Ci}`` companion, filled by a ``set_comp`` argument,
    for a generator that wanted the complement embedded beside the bit.  No
    generator does: ``bfpda``'s node marker is a constant that never depends
    on the bit, and ``nocomment`` computes each complement at runtime from
    ``{Xi}`` with its ``s``-as-NOT-gate, so the placeholder never appeared in
    a template and every caller passed a ``set_comp`` nothing consumed.
    """
    if not callable(set_bit):
        # A bit past the last pair fills nothing, as a bit past the last
        # slot always has: the suites fill a lone ``{Xi}`` with n bits.
        pairs = set_bit
        set_bit = lambda i, bit: pairs[i][bit] if i < len(pairs) else ""  # noqa: E731
    for i, bit in enumerate(bits):
        template = template.replace("{X" + str(i) + "}", set_bit(i, bit))
    return template


def permute_truth_table(truth_table: str, perm: tuple[int, ...]) -> str:
    """Rewrite ``truth_table`` so level ``k`` splits on original input ``perm[k]``.

    A decision tree splits on its inputs in a fixed order, but *which* order
    is free: the function is the same however its arguments are named.  This
    returns the table of the same function with the inputs renamed, so a
    walker that always splits most-significant-first ends up testing
    ``perm[0]`` at the root, ``perm[1]`` below it, and so on.

    The point is :func:`decision_tree_tokens`'s ``collapse`` (and the
    equivalent fold in the private recursions): a subtree folds to a leaf
    only when the rows it covers agree, and which rows a subtree covers is
    exactly what the split order decides.  ``11110000`` folds after one
    split; the same function written as ``10101010`` folds only at the
    bottom.  Reordering lets the second be emitted as the first.
    """
    _validate_truth_table(truth_table)
    return read_at(truth_table, perm, len(perm))


def essential_inputs(truth_table: str, n: int) -> list[int]:
    """Which input positions the table's value actually depends on.

    Input ``i`` matters when some row's value changes if only that bit is
    flipped; a table where none does is constant in ``i``, and an
    ``n``-input table that ignores some inputs is a smaller table wearing
    extra ones -- which is what :func:`read_at` projects it back down to.

    Three generators derived this independently before it moved here
    (``minifuck``, ``one_two_three`` and ``taglate``, the last under the
    name ``_taglate_dependencies`` and phrased over the rows where the bit
    is unset rather than over an XOR); ``home_row`` was the fourth caller
    and the point at which the spelling was worth sharing.  The two
    phrasings were checked equal over every table to ``n == 4`` before the
    duplicates were removed.
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

    Slot ``k`` of the result varies with original input ``inputs[k]``, and
    every original input not named is held at 0.  Both callers want that one
    scatter of a small row index into a wide one, and they differ only in
    whether the naming is a permutation:

    * :func:`permute_truth_table` passes all ``n`` inputs in some order, so
      nothing is held and the result is the same function with its arguments
      renamed.
    * :func:`~esolangs.tools.minifuck._project` passes the
      *essential* inputs of a table that ignores the rest.  Holding an
      ignored input at 0 is exactly right there, since by construction it
      cannot change the answer -- which is what makes an ``n``-input table
      that ignores some inputs a smaller table wearing extra ones.

    ``n`` is passed rather than derived because the projecting caller's
    result is narrower than its input: ``len(inputs)`` is the *output* width
    and ``n`` the table's own, and the two coincide only for a permutation.
    Validation stays with the callers for the same reason -- minifuck
    projects tables it has already validated, and revalidating a narrowed
    table here would check the wrong width.
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

    A level whose two halves agree everywhere cannot change the answer, so
    the tree never tests it and the read that fetched it can be discarded.
    What survives is everything else.

    The subtlety is the two frames.  ``truth_table`` is already permuted, so
    the fold is computed in *level* space -- level ``k`` splits on bit
    ``n - 1 - k`` of the permuted table -- while the reads run in *stream*
    order, over the inputs as the program consumes them.  Level ``k`` reads
    input ``perm[k]``, so the answer is translated back through ``perm``
    before it is returned; mixing the frames stores the wrong bits.
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

    Returns ``(used, width, inverted)``: the essential inputs, their count,
    and whether the table was complemented -- everything the caller needs to
    finish, since the seed and the final flip are per-language.

    The walk is the part every sum-of-minterms generator repeats: reduce to
    the essential inputs, complement when that makes fewer rows, skip the
    ``0`` rows, and for each survivor turn its literals into factors, fold
    them into a product, and add that to the sum.  ``literal(input,
    negated)`` names one factor *by original input index*, so a caller never
    sees the reduced frame's slots.

    Contrast :func:`minterm_literals`, which shares only one row's
    selection; this shares the enumeration around it.

    ``literal`` may emit as a side effect -- Collatz Multiverse allocates a
    register and writes a line for each non-negated input -- because the
    callbacks are invoked in exactly the order the hand-written loops used:
    every literal of a row, then its product, then the accumulate.  A
    callback that numbers something would drift otherwise.

    **What this deliberately cannot do.**  ROTfuck enumerates *all* rows
    rather than the 1-rows, in three separate passes over the table
    (complements, then mismatch counts, then accumulation), so its rows are
    not visited once each; Grapheme builds both sides and keeps the shorter,
    which is a choice above this loop rather than inside it; and Circuit
    Diagram routes a bus pair per literal onto a plane instead of naming a
    factor.  All three keep their own arithmetic.
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

    ``build(permuted_table, perm)`` emits the program that splits on
    ``perm[k]`` at level ``k``, reading the *permuted* table -- so every row
    index inside the build is in the permuted frame and self-consistent, and
    ``perm`` surfaces only where a node names the input it tests.

    Through :data:`_GREEDY_ORDER_MAX_ARITY`, the greedy order is chosen level
    by level, scoring each remaining input by the constant subtrees it creates.
    This costs ``O(n**2 * 2**n)`` row work, so it is a bounded small-table
    optimization rather than part of the scaling path.  Wider tables use the
    identity directly.  Both orders are built inside the bounded domain,
    because per-language address and routing costs can outweigh its folds.

    The identity order is tried first and ties keep it, so a table no
    reorder improves emits exactly what it emitted before: reordering can
    only shrink a program, never grow or churn one.

    **The read order does not move.**  Only the order the tree *tests* the
    inputs in changes; the reads (or the load block, or the ``{Xi}``
    placeholders) stay in input order, so the program consumes its input
    stream exactly as it did.

    That is what rules Polynomial out: its node reads its own bit and it has
    *no addressable storage* -- one register, no tape, no variables -- so a
    bit can only be branched on before the next read overwrites it.  Whether
    a generator can be reordered is a property of the language rather than of
    what its generator emits today, so read the interpreter's op set before
    concluding a tree is stuck with its load order.  6-5 and Jaune were once
    excluded by that phrase wrongly (both have a tape and a pointer), and so
    was Bitdeque, whose ``INJECT``/``EJECT`` work the head where
    ``PUSH``/``POP`` work the tail, making it a deque.  6-5 is the case where
    hoisting has a *price* -- a pointer move per node and a normalization per
    stored input -- so it keeps its node-read build as one more candidate and
    measures.

    **Modulous is where that check comes back negative.**  Its stack reaches
    only the top two cells, so the escape would be to park the bits in its
    ``VAR1``-``VAR4`` variables; but ``[PSH VAR1]`` *stores* into a variable
    and the only op reading one is ``[PRT VAR1 INT]``, which prints it.
    Every conditional inspects the stack top alone, and ``ADD``/``SUB`` and
    ``JMP ... IF`` all reject a variable operand, so a variable can be
    computed on and never read back -- the round trip has no return leg.
    Verified against both this repo's interpreter and the wiki.
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

    At each level every input still unchosen is scored by the number of
    constant subtrees splitting on it would produce among the blocks still
    live, and the best-scoring one is taken.  That is a direct proxy for
    what order selection seeks -- a constant subtree is the leaf a fold
    emits -- without pretending to model language-specific routing costs.

    Ties keep the lowest input index, so a table no order helps yields the
    identity and the caller emits exactly what it emitted before.
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

    ``leaf(level, row)`` returns the tokens for a leaf reached at ``level``
    standing for table entry ``row``; ``node(level, zero, one, at)``
    combines two finished subtrees, given the level it sits at and the index
    it begins at.  The walk is *post-order*: both children are complete
    before their parent runs.

    That is the whole contract, and it is what makes the shared skeleton
    worth having -- the recursion, the row split, and the running index are
    the same in every generator, while what a node and a leaf *say* is not.

    ``collapse`` returns a leaf as soon as a subtree's rows agree, so a
    constant slice emits no branching.

    **The index.**  A language with jumps needs to know where a subtree
    *lands*, not just what it says.  ``start`` is the index the whole tree
    begins at and ``parent_width`` how many tokens a node spends before its
    children -- a constant, or a function of the level when a node's own
    width grows with depth, as RAM0's address run does.  So ``at`` is the
    absolute index of the subtree ``node`` is building, which is what lets
    Bitdeque, RAM0 and S*bleq name the index their one-subtree starts at.
    All three used to reserve a slot, recurse, and backpatch it; the index
    arrives up front instead.

    **What this deliberately cannot do**, with the generator each rules out:

    * A node acts only *after* both children, never between them.  6-5,
      Jaune and Interprogck8 allocate a branch label between the two
      recursive calls, and Polynomial appends to a shared buffer while
      threading the running cell value.
    * Nothing is threaded *down* the walk, so CV(N)(C)'s accumulator,
      Jaune's held bit and entry cell, and Circlefuck's pointer position --
      each a function of the branch taken above -- have nowhere to live.
    * The zero subtree is laid down first.  Between, CV(N)(C), Unsquare and
      Interprogck8 emit their *one* subtree first, so the indices threaded
      here would reach their children swapped on any table whose subtrees
      differ in size.
    * Rows split most-significant-first, keeping each subtree contiguous.
      Modulous and Unsquare walk their bits the other way.
    * The tree is a token *sequence*, laid out by nesting.  Eval and Forth
      store theirs in a positional heap -- children pinned at
      ``2i+1``/``2i+2`` -- so a folded subtree has to be blanked in place
      rather than deleted, and concatenating variable-length subtrees is
      exactly what breaks that.
    * Both children are always built.  AddSubJump and Jaune drop an input no
      node tests and descend into one half alone, and a ``node`` discarding
      the other half still pays for the tokens the walk built: measured on
      AddSubJump, 24 of 256 tables came out longer at ``n == 3``.
    * Lamfunc returns one plain string with no index to thread.
    * The grid generators' tree is a placement on a plane rather than a
      token sequence.

    Contrast :func:`decision_tree_program`, which shares an entire finished
    construction between two dialects of one language family; this shares
    only the skeleton and takes the emitting as callbacks.
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

    Shared by the Brainfuck and Dimensional tree generators, which differ
    only in how a move is spelled: ``right``/``left`` are the tokens that
    step the pointer one cell up/down (``>``/``<`` for Brainfuck, ``>0``/
    ``<0`` for Dimensional, whose bare moves would read the cell value as
    the dimension).  Everything else -- the cell layout and the tree itself
    -- is identical.

    Each input is read and normalized to 0/1 into cell ``2i``, and cell
    ``2i + 1`` is that node's flag.  A node sets the flag, tests ``[b]`` for
    the one-side and clears the flag inside it, then tests ``[flag]`` for the
    zero-side: the flag carries "the one-side did not run" across, so exactly
    one side fires.  Each loop clears what it tested before its ``]``, so it
    exits after one pass and leaves both cells zero for the nodes below; the
    result cell is never a guard, so nothing on the way out has to see it.
    The tree is O(2**n) characters, sharing the bit tests.

    The flag is computed where it is used, not ahead of time.  This used to
    be a precomputed complement ``1 - b`` per input, built above the tree
    through two temp cells -- correct, but O(n**2) characters, since each
    input's construction walked out to the temps and back.  That cost fell
    on every table, and dominated the sparse ones, whose trees are almost
    entirely folded away: n == 10 sparse went from 2,646 characters to 754.

    A leaf only *records* its bit -- a ``'1'`` leaf is one ``+`` on the result
    cell and a ``'0'`` leaf emits nothing at all -- and the single ``.`` sits
    below the tree, where the ASCII offset is paid once.  Printing at the leaf
    instead cost ``_ASCII_ZERO`` characters per leaf, which on a dense table
    was most of the program.  Together the two take n == 10 xor from 77,939
    characters to 18,495.

    A subtree whose rows all agree collapses to a leaf rather than branching
    on bits that cannot change the answer: the side jumps straight to the
    result cell, or is dropped entirely when its value is ``'0'``.  This is
    what the deepest level always did -- a one-row span is trivially
    constant -- lifted to any level, so a table like ``11110000`` spends one
    leaf per half instead of a full tree.  The inputs are still all read (the
    reads are unconditional, above the tree), so a folded program consumes
    its input the same way an unfolded one does.  Factor is the generator
    that most wants this: it encodes this program as an integer and refuses
    tables whose encoding exceeds Python's digit limit, so folding -- and now
    the print-once leaf -- turns some previously unrenderable tables into
    runnable ones.
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

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame.  ``perm`` is spent in exactly one place -- the cell a
    node tests, ``2 * perm[i]``, with that node's flag at ``2 * perm[i] + 1``.
    The reads above the tree run over the inputs in their own order and are
    untouched by it.
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

        ``combo`` has the bits above level ``i`` set, so the subtree covers
        the ``2**(n - i)`` rows that agree with it there -- a contiguous run,
        since rows split most-significant-first.
        """
        span = 2 ** (n - i)
        rows = truth_table[combo : combo + span]
        return rows[0] if len(set(rows)) == 1 else None

    def branch(i: int, combo: int) -> None:
        """Emit one side of node ``i``: a leaf when constant, else a subtree.

        A ``'1'`` leaf is a single ``+`` on the result cell; a ``'0'`` leaf
        emits nothing at all, because the result cell is already zero and the
        arm's own guard clear is enough to exit.  Either way the arm is
        pointer-neutral, so the guard-cell dance around it is unchanged and
        only the depth the leaf is reached at differs.
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

        The flag cell carries "the one-side did not run" into the zero-side,
        which is what the precomputed complement used to do.  Entered at
        ``bit`` with the flag cell zero, left at the flag cell with both
        zero again, so nodes nest.
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

    A Collatz Multiverse line ``v = a x + b`` applies the Collatz rule to
    ``v``'s current value: an odd (or zero) value becomes ``value * a + b``
    and an even value halves.  A fresh register (value 0) therefore copies
    any built constant ``b`` with ``v = negativeOne x + b``, and when the
    copied value is *odd* a second line ``v = a x + c`` turns it into
    ``b * a + c``.  Each constant costs two lines once its operands exist, so
    a value ``n`` is reachable as ``b * a + c`` with an odd ``b``.  This
    reaches large values in O(log) constants instead of the +1/+2 chain.
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

    ``k1``/``k2`` are bootstrapped from ``negativeOne``, then each further
    constant is built by the two-line multiply-add trick from
    :func:`_extend_plans` (``k{n} = negativeOne x + k{b}`` copies the odd
    ``b``, ``k{n} = k{a} x + k{c}`` multiplies it by ``a`` and adds ``c``).
    Only the constants the program actually references are built, rather than
    a full ``1..maxval`` chain.
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
