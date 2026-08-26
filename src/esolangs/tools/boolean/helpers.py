"""Shared helpers for the boolean-function program generators.

The generators in this package build programs that read ``n`` boolean
inputs and print the result of a truth table; the helpers here are the
common input handling they all repeat.

A truth table's length determines its input count: a valid table has
``2**n`` entries, so ``n`` is recovered from the table alone and the
generators take no ``n`` parameter.
"""

from collections.abc import Callable

# ``ord("0")``.  Input digits arrive as 48/49 from a byte-oriented read, and a
# result prints as ``_ASCII_ZERO + bit``, so this offset appears in every
# generator that reads or writes a digit.  Named because a bare ``48`` in a run
# of ``+`` or ``-`` reads as a magic number.
_ASCII_ZERO = 48
_ASCII_ONE = _ASCII_ZERO + 1  # ``ord("1")``, the digit the other branch prints


def _validate_truth_table(truth_table: str) -> int:
    """Validate a truth table and return its input count ``n``.

    A valid table has ``2**n`` binary entries, so ``n`` is recovered from
    the length (a power of two).
    """
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    return n


def _complement(truth_table: str) -> str:
    """Return the bitwise complement of ``truth_table``."""
    return "".join("1" if c == "0" else "0" for c in truth_table)


def _maybe_complement(truth_table: str) -> tuple[str, bool]:
    """Return the table (or its complement) and whether it was flipped.

    A table with more ones than zeros is cheaper to evaluate complemented
    and inverted, so generators flip when ones dominate.
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


def instantiate(template: str, bits: list[int], set_bit: SetBit) -> str:
    """Substitute each ``{Xi}`` placeholder.

    ``{Xi}`` becomes ``set_bit(i, bit)``, the language's code for setting
    input ``i`` to the bit.

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
    :func:`~esolangs.tools.boolean.examples.bio` (``0oz;``) and
    ``bfstack`` (a four-character run proved minimal by exhaustive search over
    ``<>@[]``) are the worked examples.

    There used to be a ``{Ci}`` companion, filled by a ``set_comp`` argument,
    for a generator that wanted the complement embedded beside the bit.  No
    generator does: ``bfpda``'s node marker is a constant that never depends
    on the bit, and ``nocomment`` computes each complement at runtime from
    ``{Xi}`` with its ``s``-as-NOT-gate, so the placeholder never appeared in
    a template and every caller passed a ``set_comp`` nothing consumed.
    """
    for i, bit in enumerate(bits):
        template = template.replace("{X" + str(i) + "}", set_bit(i, bit))
    return template


Leaf = Callable[[int, int], list[str]]
Node = Callable[[int, list[str], list[str], int], list[str]]


def decision_tree_tokens(
    truth_table: str,
    leaf: Leaf,
    node: Node,
    *,
    parent_width: int | Callable[[int], int] = 0,
    start: int = 0,
    collapse: bool = False,
) -> list[str]:
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
    Bitdeque and RAM0 name the index their one-subtree starts at.  Both used
    to reserve a slot, recurse, and backpatch it; the index arrives up front
    instead.

    **What this deliberately cannot do**, with the generator each rules out:

    * A node acts only *after* both children, never between them.  6-5
      allocates its branch label between the two recursive calls and
      Polynomial appends to a shared buffer while threading the running cell
      value, so both need a hook this does not offer; giving them one turns
      the walker back into the recursion with more moving parts.
    * The zero subtree is laid down first.  Between emits its *one* subtree
      first, so the indices threaded here would reach its children swapped
      and every branch line would name the wrong target -- on any table
      whose two subtrees differ in size.  Which side goes first is a
      language's own business, so Between keeps its own arithmetic.
    * Rows split most-significant-first, keeping each subtree contiguous.
      Modulous walks its bits the other way, so its halves are not runs.
    * Lamfunc returns one plain string with no index to thread, so it would
      spend a one-element list at every use to gain four lines.
    * The grid generators' tree is a placement on a plane, not a token
      sequence, and none of this applies to them.

    Contrast :func:`decision_tree_program`, which shares an entire finished
    construction between two dialects of one language family; this shares
    only the skeleton and takes the emitting as callbacks.
    """
    n = _validate_truth_table(truth_table)
    width = parent_width if callable(parent_width) else lambda _level: parent_width

    def walk(level: int, lo: int, hi: int, at: int) -> list[str]:
        values = {truth_table[r] for r in range(lo, hi)}
        if level == n or (collapse and len(values) == 1):
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
    the dimension).  Everything else -- the cell layout, the complement
    construction, and the tree itself -- is identical.

    Each input is read and normalized to 0/1 into cell ``2i``, its
    complement ``1 - b`` into cell ``2i + 1`` (via two temp cells at ``2n``
    and ``2n + 1``), and a node tests ``[b]`` for the one-side and
    ``[1 - b]`` for the zero-side: the complement guards naturally exclude
    the sibling, so only the matching leaf fires.  Each branch clears its
    guard cell before its ``]``, so the loop exits after one pass, and a
    fired leaf clears the result cell, so every ``]`` on the way out sees
    zero.  The tree is O(2**n) characters, sharing the bit tests.
    """
    n = _validate_truth_table(truth_table)

    cells: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        delta = target - pos
        cells.append(right * delta if delta >= 0 else left * -delta)
        pos = target

    # read bits b_i at cell 2i, leaving the complements (cells 1, 3, ...) zero
    for i in range(n):
        cells.append(",")
        cells.extend("-" * _ASCII_ZERO)
        if i < n - 1:
            move(pos + 2)

    # complements nb_i = 1 - b_i at cell 2i+1 (t1, t2 at 2n, 2n+1)
    for i in range(n):
        move(2 * n)
        cells.append("[-]")
        move(2 * n + 1)
        cells.append("[-]")
        move(2 * i)
        cells.append("[")
        move(2 * n)
        cells.append("+")
        move(2 * n + 1)
        cells.append("+")
        move(2 * i)
        cells.append("-")
        cells.append("]")  # b -> t1, t2
        move(2 * i + 1)
        cells.append("+")  # nb = 1
        move(2 * n + 1)
        cells.append("[")
        move(2 * i + 1)
        cells.append("-")
        move(2 * n + 1)
        cells.append("-")
        cells.append("]")  # nb -= t2
        move(2 * n)
        cells.append("[")
        move(2 * i)
        cells.append("+")
        move(2 * n)
        cells.append("-")
        cells.append("]")  # restore b from t1

    # decision tree: node i entered at cell 2i, exits at cell 2i+1
    result = 2 * n + 2

    def leaf(value: str) -> None:
        cells.extend("+" * (_ASCII_ZERO + int(value)))
        cells.append(".")
        cells.append("[-]")  # clear the result so every ] on the way out sees zero

    def node(i: int, combo: int) -> None:
        bit = 2 * i
        nxt = result if i == n - 1 else bit + 2
        move(bit)
        cells.append("[")  # one-side: if b_i
        move(nxt)
        if i == n - 1:
            leaf(truth_table[combo | (1 << (n - 1 - i))])
        else:
            node(i + 1, combo | (1 << (n - 1 - i)))
        move(bit)
        cells.append("[-]")  # clear b_i so this ] exits
        cells.append("]")
        move(bit + 1)
        cells.append("[")  # zero-side: if 1 - b_i
        move(nxt)
        if i == n - 1:
            leaf(truth_table[combo])
        else:
            node(i + 1, combo)
        move(bit + 1)
        cells.append("[-]")  # clear the complement so this ] exits
        cells.append("]")

    node(0, 0)
    return "".join(cells)
