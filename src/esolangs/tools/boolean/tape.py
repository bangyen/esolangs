"""Boolean-function generators for tape-based languages."""

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import permutations

# rotfuck and six_five each own a file because their construction (a
# per-position rotation, an assembler) dwarfs the rest of the category, and
# dimensional keeps one for its pinned-dimension moves; they are re-exported
# here so this module stays the import site the package and tests already use.
from esolangs.tools.boolean.dimensional import dimensional, dimensional_tree
from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _ORDER_SEARCH_MAX,
    _validate_truth_table,
    best_input_order,
    decision_tree_program,
    stored_inputs,
)
from esolangs.tools.boolean.rotfuck import rotfuck
from esolangs.tools.boolean.six_five import six_five
from esolangs.tools.boolean.slow_acv_mammalian import slow_acv_mammalian_boolean
from esolangs.tools.text.tape import _factor_encode

__all__ = [
    "basicfuck",
    "bf_tree",
    "brainfuck",
    "brainif",
    "circlefuck",
    "circlefuck_byte",
    "dimensional",
    "dimensional_tree",
    "factor",
    "jaune",
    "jaune_multiply",
    "painfuck",
    "rotfuck",
    "sbleq",
    "six_five",
    "slow_acv_mammalian_boolean",
    "suffolk",
    "three_d_brainfuck",
]


@dataclass
class _Cmd:
    """A line emitted verbatim, apart from its ``goto`` placeholder."""

    text: str


@dataclass
class _If:
    """An ``if <char> goto <label>`` line, resolved once labels are known."""

    char: int
    label: int


@dataclass
class _MoveRight:
    """An ``if <char> move right`` line that also *defines* ``label``."""

    char: int
    label: int


@dataclass
class _MoveLeft:
    """An ``if <char> move left`` line that also *defines* ``label``.

    The mirror of :class:`_MoveRight`, for a tree whose branches walk *down*
    the tape: BrainIf reads its inputs from the far cell back toward the
    answer, so a branch steps left onto the next input rather than right.
    """

    char: int
    label: int


@dataclass
class _Out:
    """A marker defining output routine ``which``; it emits no line itself."""

    which: int


@dataclass
class _End:
    """The trailing blank line every program ends on."""


_Entry = _Cmd | _If | _MoveRight | _MoveLeft | _Out | _End


def brainif(truth_table: str) -> str:
    """Build a BrainIf program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    BrainIf reads each input into a cell with ``if 0 input``, then a
    recursive decision tree checks each cell with ``if 48/49 goto`` (the
    groups' checks sit adjacent so a failed check falls through to the next
    candidate).

    The answer byte is built *first*, on cell 0: 48 ``increment`` lines
    once, rather than a climb per digit.  There is no way to copy a byte in
    BrainIf, and a climb of ``if v increment`` lines converges -- every
    entry value 0..47 leaves it holding 48 -- so one climb cannot serve both
    digits however it is entered.  Two climbs is 48 + 49 lines, which used
    to dominate: a ``11110000`` program was 97 increments out of 153 lines.

    **Every line is gated on an exact cell value, which constrains how the
    pointer may move.**  A step whose starting digit is unknown needs both
    guards, and the two lines test *different* cells -- the second runs after
    the first has already moved -- so a guarded pair over written cells fires
    twice whenever the neighbouring digits differ.  The pair is sound only
    when the destination is still zero, which is why the original
    construction reads on the way out and tests on the way back: every cell
    the pointer lands on during the tree phase is unwritten.

    Two spellings escape that.  A cell whose digit the code *knows* -- the
    arm of a branch that just tested it -- moves in one line.  A cell that is
    **dead** (already tested, never tested again) moves in two by
    normalizing first::

        if 48 increment   # 48 -> 49, a 49 is untouched: the cell is now 49
        if 49 move left   # so exactly one move fires

    Cell 0 is the one exception: it holds the answer byte, which must stay 48
    until a leaf increments it, so the walk home never normalizes it.

    **The tree splits on its inputs in whichever order the language can
    reach**, which is not all ``n!`` of them.  Reads happen in input order,
    and a written cell cannot be crossed without destroying it, so the
    pointer's placement is monotone: the reachable orders are exactly the
    ``n + 1`` *j-splits* -- hoist inputs ``0..j-1`` into cells while walking
    out, node-read inputs ``j..n-1`` as before, and the test order is then
    ``(j, ..., n-1, j-1, ..., 0)``.  ``j = 0`` is the node-read construction
    and ``j = n`` hoists everything.  Like Unsquare, the reachable set *is*
    the candidate list rather than a filter over a larger one.

    All ``n + 1`` are built and the shortest kept, the node-read build first
    so a tie preserves today's emission.  Measured 5.2% at n=3 (194 of 256
    tables improved, none grown) and 7.4% at n=4.
    """
    n = _validate_truth_table(truth_table)
    candidates = [_brainif_node_read(truth_table)]
    candidates += [_brainif_jsplit(truth_table, j) for j in range(1, n + 1)]
    return min(candidates, key=lambda program: len(program.splitlines()))


def _brainif_jsplit(truth_table: str, j: int) -> str:
    """Emit the j-split BrainIf program; see :func:`brainif`.

    Inputs ``0..j-1`` are read up front into cells ``1..j`` while the pointer
    walks out over still-zero cells; inputs ``j..n-1`` are read at their
    nodes as the tree walks back down.  The test order is therefore
    ``(j, ..., n-1, j-1, ..., 0)``.
    """
    n = _validate_truth_table(truth_table)
    order = list(range(j, n)) + list(range(j - 1, -1, -1))
    entries: list[_Entry] = [_Cmd(f"if {v} increment") for v in range(_ASCII_ZERO)]
    entries.append(_Cmd(f"if {_ASCII_ZERO} move right"))
    # The read-out pair is sound because each step lands on an unwritten cell.
    for i in range(j):
        entries.append(_Cmd("if 0 input"))
        if i < j - 1 or j < n:
            entries.append(_Cmd(f"if {_ASCII_ZERO} move right"))
            entries.append(_Cmd(f"if {_ASCII_ONE} move right"))
    entries += [_Cmd("if 0 move right") for _ in range(max(0, n - j - 1))]

    counter = [0]

    def build(rows: list[int], k: int, pos: int) -> list[_Entry]:
        """Emit the subtree testing ``order[k]``, pointer on that input's cell."""
        if k == n or len({truth_table[row] for row in rows}) == 1:
            out: list[_Entry] = []
            cell = pos
            # Consume the reads this path skipped; a skipped node-read lands
            # on a zero cell, so its step is the sound guarded pair.
            for level in range(k, n):
                if order[level] < j:
                    continue
                out.append(_Cmd("if 0 input"))
                if cell > 0:
                    out.append(_Cmd(f"if {_ASCII_ZERO} move left"))
                    out.append(_Cmd(f"if {_ASCII_ONE} move left"))
                    cell -= 1
            # The rest of the walk crosses dead cells, which normalize first;
            # the final step onto cell 0 must not, so it stays a plain pair.
            while cell > 1:
                out.append(_Cmd(f"if {_ASCII_ZERO} increment"))
                out.append(_Cmd(f"if {_ASCII_ONE} move left"))
                cell -= 1
            if cell == 1:
                out.append(_Cmd(f"if {_ASCII_ZERO} move left"))
                out.append(_Cmd(f"if {_ASCII_ONE} move left"))
            if int(truth_table[rows[0]]):
                out.append(_Cmd(f"if {_ASCII_ZERO} increment"))
            out.append(_Cmd(f"if {_ASCII_ZERO} goto OUT0"))
            out.append(_Cmd(f"if {_ASCII_ONE} goto OUT0"))
            return out
        pre: list[_Entry] = []
        if order[k] >= j:
            pre.append(_Cmd("if 0 input"))
        l0, l1 = counter[0], counter[0] + 1
        counter[0] += 2
        bit = n - 1 - order[k]
        g0 = [row for row in rows if not ((row >> bit) & 1)]
        g1 = [row for row in rows if (row >> bit) & 1]
        return [
            *pre,
            _If(_ASCII_ZERO, l0),
            _If(_ASCII_ONE, l1),
            _MoveLeft(_ASCII_ZERO, l0),
            *build(g0, k + 1, pos - 1),
            _MoveLeft(_ASCII_ONE, l1),
            *build(g1, k + 1, pos - 1),
        ]

    entries += build(list(range(2**n)), 0, n if j < n else j)
    entries.append(_Out(0))
    entries.append(_Cmd(f"if {_ASCII_ZERO} output"))
    entries.append(_Cmd(f"if {_ASCII_ONE} output"))
    entries.append(_End())
    return _brainif_render(entries)


def _brainif_node_read(truth_table: str) -> str:
    """Emit the node-read BrainIf program; see :func:`brainif`.

    Every input is read at the node that tests it, so the reads carry the
    pointer home and a leaf is already standing on the answer cell.  This is
    the ``j = 0`` member of the j-split family, kept first in the dispatch so
    a tie preserves the emission this generator has always produced.
    """
    n = _validate_truth_table(truth_table)
    entries: list[_Entry] = []
    # The answer byte goes on cell 0 and the inputs above it, read from the
    # far end back down.  Building first means stepping out over cells that
    # are still zero, where one ``if 0 move right`` advances exactly one
    # cell -- no digit is around to fire the next line as well.
    entries += [_Cmd(f"if {v} increment") for v in range(_ASCII_ZERO)]
    entries.append(_Cmd(f"if {_ASCII_ZERO} move right"))
    entries += [_Cmd("if 0 move right") for _ in range(n - 1)]

    counter = [0]

    def build(rows: list[int], k: int) -> list[_Entry]:
        """Emit the subtree for ``rows``, entered with the pointer on cell n-k+1."""
        rest = n - (k - 1)
        if rest == 0 or len({truth_table[row] for row in rows}) == 1:
            # Consume the inputs this path never branched on, which walks
            # the pointer the rest of the way home; then add one iff the
            # answer is a 1 and join the tail.  Reading them is not optional:
            # a program whose input count depended on its table would desync
            # a caller feeding several programs from one stream.
            out: list[_Entry] = []
            for _ in range(rest):
                out.append(_Cmd("if 0 input"))
                out.append(_Cmd(f"if {_ASCII_ZERO} move left"))
                out.append(_Cmd(f"if {_ASCII_ONE} move left"))
            if int(truth_table[rows[0]]):
                out.append(_Cmd(f"if {_ASCII_ZERO} increment"))
            out.append(_Cmd(f"if {_ASCII_ZERO} goto OUT0"))
            out.append(_Cmd(f"if {_ASCII_ONE} goto OUT0"))
            return out
        # Level ``k`` reads input ``k - 1`` into cell ``n - k + 1``, so the
        # bit it selects is the table's usual most-significant-first one --
        # the reads are in input order even though the pointer walks down.
        g0 = [row for row in rows if ((row >> (n - k)) & 1) == 0]
        g1 = [row for row in rows if ((row >> (n - k)) & 1) == 1]
        l0, l1 = counter[0], counter[0] + 1
        counter[0] += 2
        sub0 = build(g0, k + 1)
        sub1 = build(g1, k + 1)
        return [
            _Cmd("if 0 input"),
            _If(_ASCII_ZERO, l0),
            _If(_ASCII_ONE, l1),
            _MoveLeft(_ASCII_ZERO, l0),
            *sub0,
            _MoveLeft(_ASCII_ONE, l1),
            *sub1,
        ]

    entries += build(list(range(2**n)), 1)
    # One shared tail: the answer cell already holds the byte to print, so
    # this is two lines rather than a climb per digit.
    entries.append(_Out(0))
    entries.append(_Cmd(f"if {_ASCII_ZERO} output"))
    entries.append(_Cmd(f"if {_ASCII_ONE} output"))
    entries.append(_End())

    return _brainif_render(entries)


def _brainif_render(entries: list[_Entry]) -> str:
    """Resolve labels and emit the program text for a BrainIf entry list."""
    # resolve labels from the actual line sequence (the "out" markers emit
    # no line, so the marker's target is the next line that does)
    labels: dict[int, int] = {}
    out_labels: dict[int, int] = {}
    line_no = 0
    pending: int | None = None
    for entry in entries:
        if isinstance(entry, _Out):
            pending = entry.which
            continue
        line_no += 1
        if pending is not None:
            out_labels[pending] = line_no
            pending = None
        if isinstance(entry, _MoveRight | _MoveLeft):
            labels[entry.label] = line_no
    end_line = line_no + 1

    lines: list[str] = []
    for entry in entries:
        if isinstance(entry, _Cmd):
            text = entry.text
            if "goto OUT" in text:
                # keep the line's own guard: a leaf reaches the tail from a
                # cell holding 48 or 49, so it emits one goto for each
                guard, target = text.split(" goto OUT")
                text = f"{guard} goto {out_labels[int(target)]}"
            elif "goto end" in text:
                text = text.replace("goto end", f"goto {end_line}")
            lines.append(text)
        elif isinstance(entry, _If):
            lines.append(f"if {entry.char} goto {labels[entry.label]}")
        elif isinstance(entry, _MoveRight):
            lines.append(f"if {entry.char} move right")
        elif isinstance(entry, _MoveLeft):
            lines.append(f"if {entry.char} move left")
        elif isinstance(entry, _Out):
            continue
        else:
            lines.append("")
    return "\n".join(lines)


def circlefuck(truth_table: str) -> str:
    """Build a Circlefuck program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Circlefuck reads each input with ``,`` and normalizes it to 0/1 with 48
    ``-``s, then a decision tree branches on the cells from the last input
    down. Each leaf starts from a cleared cell, so it sets the result with
    ``+``s, prints it, and halts with ``@`` -- halting at the leaf means the
    tree never needs to skip the sibling branch.  A boolean table is just
    the byte-valued generator with ``48 + bit`` outputs.

    A subtree whose rows all agree folds to a leaf; see
    :func:`circlefuck_byte`, which both share.
    """
    return circlefuck_byte([_ASCII_ZERO + int(bit) for bit in truth_table])


def circlefuck_byte(truth_table: Sequence[int]) -> str:
    """Build a Circlefuck program computing a byte-valued function.

    ``truth_table`` is a sequence of ``2**n`` byte values (0-255) indexed by
    the inputs (most significant first); the input count ``n`` is implied
    by the table length.  This is the boolean generator generalized to
    arbitrary byte outputs: each leaf prints ``chr(value)`` instead of
    ``chr(48 + bit)``.

    A subtree whose rows all agree becomes a leaf rather than branching on
    bits that cannot change the answer.  The reads sit above the tree and
    are unconditional, so a folded program consumes its input exactly as an
    unfolded one does.

    **The tree splits on its inputs in whichever order emits the shortest
    program**, over all ``n!`` of them.  Unlike the generators whose nodes
    *name* the input they test, a Circlefuck node tests whatever cell the
    pointer is over, so an order is not a renaming: the tree has to walk
    the pointer to the cell it wants, and the walk is a real cost the fold
    has to beat.  See :func:`_circlefuck_ordered`.
    """
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
    return _best_byte_order(truth_table, n)


def _permute_byte_table(truth_table: Sequence[int], perm: tuple[int, ...]) -> list[int]:
    """Return ``truth_table`` re-indexed so input ``perm[i]`` sits at position ``i``.

    Row ``r`` of the result holds the value the original table gives when
    input ``perm[i]`` carries bit ``i`` of ``r`` -- the permuted frame
    :func:`~esolangs.tools.boolean.helpers.best_input_order` documents, in
    which every row index inside the build is self-consistent.
    """
    n = len(perm)
    out = [0] * len(truth_table)
    for row in range(len(truth_table)):
        source = 0
        for i in range(n):
            bit = (row >> (n - 1 - i)) & 1
            source |= bit << (n - 1 - perm[i])
        out[row] = truth_table[source]
    return out


def _best_byte_order(truth_table: Sequence[int], n: int) -> str:
    """Return the shortest program over every input order.

    The byte-valued twin of
    :func:`~esolangs.tools.boolean.helpers.best_input_order`, which takes a
    binary *string*; the search and its guarantees are the same.  The
    identity order goes first and ties keep it, so a table no reorder helps
    emits exactly what it emitted before.

    The search is capped for the same reason the shared helper caps: ``n!``
    builds of an ``O(2**n)`` program.  Circlefuck's byte tables come from
    the text generator at ``n <= 8``, so the cap is reached in practice and
    the greedy fallback is not decorative.
    """
    best = _circlefuck_ordered(list(truth_table), tuple(range(n)))
    if n < 2:
        return best
    if n > _ORDER_SEARCH_MAX:
        return min(best, _circlefuck_greedy(truth_table, n), key=len)
    for perm in permutations(range(n)):
        if perm == tuple(range(n)):
            continue
        candidate = _circlefuck_ordered(_permute_byte_table(truth_table, perm), perm)
        if len(candidate) < len(best):
            best = candidate
    return best


def _circlefuck_greedy(truth_table: Sequence[int], n: int) -> str:
    """Pick an order level by level above the exhaustive cap.

    Each remaining input is scored by how many constant subtrees choosing
    it next would create -- the fold the exhaustive search is hunting --
    which is ``O(n**2)`` scorings rather than ``n!`` builds.
    """
    remaining = list(range(n))
    order: list[int] = []
    while remaining:
        best_input = max(
            remaining,
            key=lambda i: _constant_subtree_count(truth_table, n, [*order, i]),
        )
        order.append(best_input)
        remaining.remove(best_input)
    perm = tuple(order)
    return _circlefuck_ordered(_permute_byte_table(truth_table, perm), perm)


def _constant_subtree_count(
    truth_table: Sequence[int], n: int, prefix: list[int]
) -> int:
    """Count the subtrees that come out constant after splitting on ``prefix``.

    A subtree is the set of rows agreeing on every input in ``prefix``; it
    is constant when the table takes one value across all of them, which is
    exactly when the build folds it to a leaf.
    """
    buckets: dict[int, set[int]] = {}
    for row in range(len(truth_table)):
        key = 0
        for i in prefix:
            key = (key << 1) | ((row >> (n - 1 - i)) & 1)
        buckets.setdefault(key, set()).add(truth_table[row])
    return sum(1 for values in buckets.values() if len(values) == 1)


def _circlefuck_ordered(truth_table: list[int], perm: tuple[int, ...]) -> str:
    """Emit one input order's Circlefuck program; see :func:`circlefuck_byte`.

    ``truth_table`` is in the permuted frame -- bit ``k`` of a row index is
    the input tested at level ``k`` -- so the fold test below reads rows
    without consulting ``perm``.  ``perm`` surfaces only where the pointer
    has to be *aimed*: the inputs sit in cells ``0..n-1`` in stream order,
    and the cell level ``k`` tests is ``perm[k]``.

    **The walk is what makes this generator's reorder a real question.**  A
    node here does not name its input, it tests the cell under the pointer,
    so a level costs ``|previous cell - perm[k]|`` move characters on top
    of its branch.  The identity order is the one the walk is free for --
    it steps left one cell per level, which is the single ``<`` the
    unordered build emitted -- so any other order has to fold enough to pay
    for its moves.
    """
    n = len(perm)
    prog: list[str] = []

    def emit(c: str) -> None:
        prog.append(c)

    for _ in range(n):
        emit(",")
        prog.extend("-" * _ASCII_ZERO)
        emit(">")
    prog.pop()  # the trailing ">" would leave the pointer past the last input

    def move(source: int, target: int) -> None:
        """Walk the pointer from cell ``source`` to cell ``target``."""
        step = ">" if target > source else "<"
        prog.extend(step * abs(target - source))

    def span(k: int, row: int) -> range:
        """Return the table rows the subtree at ``(k, row)`` stands for.

        Bit ``k`` of a row index is the input tested at level ``k``, so a
        subtree entered at level ``k`` has fixed the bits above ``k`` and
        varies the ones below: its rows are the stride the unordered build
        also walked, now in the permuted frame.
        """
        step = 2 ** (n - 1 - k)
        return range(row, len(truth_table), step)

    def build(k: int, row: int, cell: int) -> None:
        """Emit the subtree at level ``k`` with the pointer over ``cell``."""
        if k < 0:
            value = truth_table[row]
            if value:
                prog.extend("+" * value)
            emit(".")
            emit("@")
            return
        if len({truth_table[r] for r in span(k, row)}) == 1:
            # Every row this subtree could reach agrees, so the bits it
            # would branch on cannot change the answer.  The reads are
            # unconditional, above the tree, so a folded program still
            # consumes its input the same way an unfolded one does.
            #
            # The ``[-]`` is what a full-depth leaf relies on: it is
            # emitted inside each ``[`` on the way down, so a leaf builds
            # its value on a cleared cell.  A folded leaf skips those
            # levels and so must clear the cell itself -- without this the
            # pointer still holds an input bit and every one-valued input
            # prints one too high.
            emit("[-]")
            build(-1, row, cell)
            return
        target = perm[k]
        move(cell, target)
        emit("[")
        emit("[-]")
        # Both arms leave the pointer wherever the deeper level put it, but
        # each arm re-aims from ``target`` itself: the ``[-]`` above cleared
        # the tested cell, so the loop runs at most once and the ``]`` is
        # reached with the pointer back under our control only if the arm
        # returns it.  Emitting the walk inside each arm rather than once
        # before the branch is what keeps the two arms independent.
        build(k - 1, row + 2 ** (n - 1 - k), target)
        emit("]")
        build(k - 1, row, target)

    build(n - 1, 0, n - 1)
    return "".join(prog)


def brainfuck(truth_table: str) -> str:
    """Build a brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    This is :func:`bf_tree`, a decision tree sharing the bit tests.

    There used to be a second construction here -- a branch-free sum of
    minterms -- and ``bf`` returned whichever came out shorter, because the
    tree was full and so paid for every input on sparse tables where the
    minterm paid only per one-row.  Once the tree started folding constant
    subtrees it won on every table at n <= 4 but the two constant ones,
    where it costs about 2.5x the minterm (629 against 253 characters at
    n == 4) -- a bounded factor on two tables out of 65536, which is not
    worth a second construction and a dispatch to choose between them.
    """
    return bf_tree(truth_table)


def factor(truth_table: str) -> str:
    """Build a Factor program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    A Factor program is a single integer whose prime factorization decodes
    to brainfuck, so the generator reuses :func:`brainfuck`'s truth-table
    program unchanged and encodes it with :func:`_factor_encode` -- the same
    prime-search the text generator uses (walk primes upward, handing each
    instruction the next one with the right residue mod 11; Dirichlet's
    theorem guarantees one always exists).

    Folding the constant subtrees of that program is what turns some
    otherwise unrenderable tables into runnable ones, since the cap below is
    on the encoded integer's size.

    This is a program-size cap, not an ``n`` cap: sparse tables (e.g. an
    all-zero or all-one table) stay small at any ``n``, while dense tables
    grow the underlying brainfuck program (and so the encoded integer)
    quickly.  CPython refuses to render an integer above
    ``sys.get_int_max_str_digits()`` decimal digits (a DoS guard, not a
    Factor property), and the Factor *interpreter* parses its input the
    same way, so a program past that limit would not just fail to print
    here -- it would fail to run.  The check estimates the digit count from
    the integer's bit length (``log10(2) ~= 0.30103``) to avoid paying for
    the same oversized conversion just to reject it.
    """
    number = _factor_encode(brainfuck(truth_table))
    limit = sys.get_int_max_str_digits()
    if limit and number.bit_length() * 0.30103 + 1 > limit:
        raise ValueError(
            "the Factor boolean generator's encoded integer would exceed "
            f"Python's {limit}-digit limit for integer-to-string conversion "
            "(sys.get_int_max_str_digits()) -- the Factor interpreter parses "
            "its program the same way, so this table's encoding could not "
            "be run even if it were rendered; try a sparser table",
        )
    return str(number)


def three_d_brainfuck(truth_table: str) -> str:
    """Build a 3D Brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    3D Brainfuck's ``>``/``<`` set the generation pointer's heading (a no-op
    in this interpreter), so the array is walked along one axis with
    ``e``/``w`` instead; :func:`brainfuck`'s decision tree otherwise
    translates directly, so this folds constant subtrees because that does.
    """
    return brainfuck(truth_table).translate(str.maketrans("><", "ew"))


# The interpreter's two substitution cycles, in the order the cross-check
# scans them: Painfuck source is pre-shifted here so the trans table recovers
# the intended commands.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def painfuck(truth_table: str) -> str:
    """Build a Painfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Painfuck is brainfuck-compatible: the commands ``a``/``b`` are while-
    nonzero loops, ``j`` reads a byte and ``u`` prints one.
    :func:`brainfuck`'s decision tree translates directly (so this folds
    constant subtrees because that does), mapping BF's
    ``>``/``<`` (each one cell) to ``rl`` (+1) / ``l`` (-1), ``+``/``-`` to
    ``ps`` (+1) / ``s`` (-1), and ``[``/``]``/``,``/``.`` to ``a``/``b``/
    ``j``/``u``.  The interpreter then rewrites the source through two
    substitution cycles, so each emitted command is pre-shifted ``k`` steps
    back along its cycle (where ``k`` counts the commands so far) to undo it.
    """
    code = (
        brainfuck(truth_table)
        .replace(">", "rl")
        .replace("<", "l")
        .replace("+", "ps")
        .replace("-", "s")
        .replace("[", "a")
        .replace("]", "b")
        .replace(",", "j")
        .replace(".", "u")
    )
    out: list[str] = []
    k = 0
    for char in code:
        for cycle in _CYCLES:
            p = cycle.find(char)
            if p != -1:
                out.append(cycle[(p - k) % len(cycle)])
                k += 1
                break
        else:
            # every command the brainfuck generator emits maps to a command
            # in _CYCLES, so this branch is unreachable by construction
            raise ValueError(
                f"Painfuck command {char!r} is not in a cycle"
            )  # pragma: no cover
    return "".join(out)


def bf_tree(truth_table: str) -> str:
    """Build a decision-tree brainfuck program for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The construction is :func:`decision_tree_program`, shared with
    :func:`dimensional_tree`.  The tree is O(2**n) characters (sharing the
    bit tests), versus the branch-free minterm evaluator's O(n * 2**n); for
    XOR-n it measures 1.4K..20K characters at n = 2..8 against the
    minterm's 1.4K..33M.
    """
    return decision_tree_program(truth_table, ">", "<")


def basicfuck(truth_table: str) -> str:
    """Build a Basicfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Basicfuck's named variables behave like BF cells with an explicit
    arithmetic, so the program is a decision tree: each input is read with
    ``read -> a_i ;`` and normalized to 0/1 with ``a_i -= 48 ;``, then every
    internal node emits ``if (a_k) { ... }`` next to ``if !(a_k) { ... }``
    (the wiki spells negation ``!(<X>)``, with the bang before the parens).  A
    failed ``if`` falls through to its neighbour, so exactly one subtree runs
    per input combination.  Each leaf adds ``48 + entry`` to the ``out``
    variable (which starts at 0 and is touched by exactly one leaf) and
    prints it with ``write <- out ;``.

    A subtree whose rows all agree becomes a leaf instead of branching on
    bits that cannot change the answer, which is what makes a table like
    ``11110000`` two leaves rather than eight.  This is safe because a leaf
    here is self-contained -- it names ``out`` and writes it, with nothing
    but cosmetic indentation depending on how deep it sits -- so the
    "exactly one leaf runs" invariant holds at any depth.  Generators whose
    leaf depends on the path that reached it cannot do this: BrainIf's
    leaves jump to a shared output routine that assumes the pointer has
    passed every level's marker, and Streetcode's hall geometry is sized
    from its subtree's height.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.boolean.helpers.best_input_order`).
    The ``read -> a_i`` block stays in input order, so only the variable an
    ``if`` names moves.
    """
    return best_input_order(truth_table, _basicfuck_ordered)


def _basicfuck_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Basicfuck program; see :func:`basicfuck`.

    The variables are 1-based (``a1``..``an``) while ``perm`` indexes from
    zero, so the level's variable is ``a{perm[k - 1] + 1}``.
    """
    n = _validate_truth_table(truth_table)

    lines = ["#basicfuck t=unbounded r=0~255 o=wrap"]
    lines.append("#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out")
    for i in range(1, n + 1):
        lines.append(f"read -> a{i} ;")
        lines.append(f"a{i} -= 48 ;")

    def build(rows: list[int], k: int, depth: int) -> str:
        indent = "  " * depth
        if len({truth_table[row] for row in rows}) == 1:
            value = int(truth_table[rows[0]])
            return f"{indent}out += {_ASCII_ZERO + value} ;\n{indent}write <- out ;\n"
        g0 = [row for row in rows if ((row >> (n - k)) & 1) == 0]
        g1 = [row for row in rows if ((row >> (n - k)) & 1) == 1]
        var = f"a{perm[k - 1] + 1}"
        return (
            f"{indent}if ({var}) {{\n"
            + build(g1, k + 1, depth + 1)
            + f"{indent}}}\n"
            + f"{indent}if !({var}) {{\n"
            + build(g0, k + 1, depth + 1)
            + f"{indent}}}\n"
        )

    lines.append(build(list(range(2**n)), 1, 0).rstrip("\n"))
    return "\n".join(lines)


def sbleq(truth_table: str) -> str:
    """Build an S*bleq program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the
    inputs (most significant first); the table length implies ``n``.

    S*bleq's instruction is ``a b c``: ``mem[a] -= mem[b]``, and when the
    result is ``<= 0`` the pointer jumps to the address stored at ``c``.
    The ``<= 0`` branch traps on zero, so a bit normalized to 0 would
    branch the wrong way; the generator instead normalizes each input to
    ``49 - byte`` (``'0'`` -> 1, ``'1'`` -> 0), which lands the two cases on
    opposite sides of zero.

    **The reads are hoisted above the tree**, which is what lets the tree
    split in any input order.  The read block is ``2n`` instructions, two
    per input::

        v_i -2   NXT    # v_i = -byte (always <= 0, so NXT is the next instr)
        v_i NEG49 NXT2  # v_i = 49 - byte; both outcomes continue to the next

    and a branch node is then a *single* instruction that tests its value
    cell against a zero constant::

        v_j ZERO ONE    # a one jumps to ONE, a zero falls through

    Subtracting zero is what makes the test **non-destructive**, so a value
    cell survives being tested and the tree may name its inputs in any
    order.  A destructive test would also work -- a root-to-leaf path tests
    each input at most once -- but only by accident of the tree's shape, and
    it would break the moment a node wanted to re-test a bit.

    Hoisting is a saving in its own right, independent of the reorder.  The
    node-read build it replaces read at each node, so every leaf had to
    *drain* the reads its untaken siblings never made -- an input-capable
    language reads each of its n inputs exactly once per run whatever the
    table says -- and that drain cost two instructions and a data triple per
    undrained level, per leaf.  The hoisted read block pays for each input
    once for the whole program.

    Leaves print ``-3 D 0`` (``D`` a constant 48/49 cell) and halt with
    ``0 0 HALT`` (``HALT`` holds -1, a negative jump target).  Whole
    subtrees whose table entries are constant collapse to a leaf.

    S*bleq's operands are addresses, so a cell holding a transient 0/1 is
    misread as a jump target if any ``c`` references it.  The generator
    therefore keeps *constant* cells (``NEG49``, ``D48``, ``D49``, ``HALT``,
    ``ZERO``, and the ``NXT``/``NXT2``/``ONE`` targets, the only cells ever
    used as a ``c`` operand) strictly separate from *value* cells (each
    input's ``v``, written by the read and never used as a ``c`` operand).
    The jump targets are back-patched once the code layout is known.  The
    normalize subtracts the constant in the ``b`` operand, which the
    ``store="b"``/``"ab"`` variants would overwrite, so this generator
    targets base S*bleq (``store="a"``).

    **Both constructions are kept as candidates** (technique 4).  Hoisting
    wins on 254 of the 256 tables at n=3, but the two constant tables are
    the exception: the node-read build folds them to a single leaf whose
    drain *is* the whole program, which comes out one character shorter than
    a read block for inputs no branch ever tests.  Keeping the older build
    in the dispatch is what makes this a pure shrink -- 24.65% at n=3 with
    nothing grown, against 24.64% if the hoisted build simply replaced it.
    """
    _validate_truth_table(truth_table)
    return min(
        best_input_order(truth_table, _sbleq_hoisted),
        _sbleq_node_read(truth_table),
        key=len,
    )


def _sbleq_hoisted(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's hoisted S*bleq program; see :func:`sbleq`.

    ``perm[k]`` is the input the tree tests at level ``k``; the read block
    stays in input order, so the program consumes its input stream exactly
    as the node-read build did.
    """
    n = _validate_truth_table(truth_table)
    neg49, d48, zero_const = 0, 1, 4
    vbase = 5
    nxtbase = vbase + n
    del d48

    # (a operand, b operand, kind, kind's argument); ``a``/``b`` are data
    # offsets made absolute below, and ``kind`` picks how ``c`` is filled.
    instructions: list[tuple[int, int, str, int]] = []
    ones: list[int] = []

    for i in range(n):
        instructions.append((vbase + i, -2, "nxt", i))
        instructions.append((vbase + i, neg49, "nxt2", i))

    def build(level: int, rows: list[int]) -> None:
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            instructions.append((-3, 1 + int(results.pop()), "out", 0))
            instructions.append((0, 0, "halt", 0))
            return
        slot = len(ones)
        ones.append(0)
        instructions.append((vbase + perm[level], zero_const, "one", slot))
        bit = n - 1 - level
        build(level + 1, [r for r in rows if not ((r >> bit) & 1)])
        ones[slot] = 3 * len(instructions)
        build(level + 1, [r for r in rows if (r >> bit) & 1])

    build(0, list(range(2**n)))

    m = len(ones)
    onebase = nxtbase + n
    nxt2base = onebase + m
    data_base = 3 * len(instructions)

    cells: list[int] = []
    for a, b, kind, arg in instructions:
        if kind == "out":
            cells += [-3, data_base + b, 0]
        elif kind == "halt":
            cells += [0, 0, data_base + 3]
        elif kind == "nxt":
            cells += [data_base + a, -2, data_base + nxtbase + arg]
        elif kind == "nxt2":
            cells += [data_base + a, data_base + b, data_base + nxt2base + arg]
        else:
            cells += [data_base + a, data_base + b, data_base + onebase + arg]

    data = (
        [-_ASCII_ONE, _ASCII_ZERO, _ASCII_ONE, -1, 0]
        + [0] * n
        + [3 * (2 * i + 1) for i in range(n)]
        + ones
        + [3 * (2 * i + 2) for i in range(n)]
    )
    cells += data
    return " ".join(map(str, cells))


def _sbleq_node_read(truth_table: str) -> str:
    """Emit the node-read S*bleq program; see :func:`sbleq`.

    Each node reads its own bit, so every leaf drains the reads its untaken
    siblings never made.  Kept as a candidate because that drain is cheaper
    than a read block on a table no node ever branches on -- the constant
    tables, where the whole program is one leaf.
    """
    n = _validate_truth_table(truth_table)

    instructions: list[tuple[int, int, int]] = []
    nodes: list[tuple[int, int, int]] = []  # (v offset, normalize addr, one addr)
    counter = 0

    def build(level: int, rows: list[int]) -> None:
        nonlocal counter
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            instructions.append((-3, 1 + int(results.pop()), 0))
            for _ in range(level, n):
                nid = counter
                counter += 1
                instructions.append((4 + nid, -2, 0))  # read; c patched to NXT
                normalize_addr = 3 * len(instructions)
                instructions.append((4 + nid, 0, 0))  # normalize; patched below
                nodes.append((nid, normalize_addr, 3 * len(instructions)))
            instructions.append((0, 0, 3))
            return
        nid = counter
        counter += 1
        instructions.append((4 + nid, -2, 0))  # read; c patched to this node's NXT
        normalize_addr = 3 * len(instructions)
        instructions.append((4 + nid, 0, 0))  # normalize; b and c patched below
        zero = [r for r in rows if not ((r >> (n - 1 - level)) & 1)]
        one = [r for r in rows if (r >> (n - 1 - level)) & 1]
        build(level + 1, zero)
        one_addr = 3 * len(instructions)
        build(level + 1, one)
        nodes.append((nid, normalize_addr, one_addr))

    build(0, list(range(2**n)))

    m = len(nodes)
    for nid, normalize_addr, _one_addr in nodes:
        instructions[normalize_addr // 3 - 1] = (4 + nid, -2, 4 + m + nid)
        instructions[normalize_addr // 3] = (4 + nid, 0, 4 + 2 * m + nid)

    data_base = 3 * len(instructions)
    cells: list[int] = []
    for a, b, c in instructions:
        if a == -3:  # output the constant at b
            cells += [-3, data_base + b, 0]
        elif a == 0 and b == 0:  # halt via the HALT constant at c
            cells += [0, 0, data_base + c]
        else:  # read/normalize: make every data-cell operand absolute
            cells += [data_base + a, -2 if b == -2 else data_base + b, data_base + c]
    data = [-_ASCII_ONE, _ASCII_ZERO, _ASCII_ONE, -1] + [0] * (3 * m)
    for nid, normalize_addr, one_addr in nodes:
        data[4 + m + nid] = normalize_addr
        data[4 + 2 * m + nid] = one_addr
    cells += data
    return " ".join(map(str, cells))


# ROTfuck rotates the whole program after every command, so a brainfuck-style
# decision tree does not survive: the bracket that fires seeks its partner in
# the *rotated* program, at a rotation state that depends on the step count.
# The construction below is the discovered escape, verified against the
# interpreter: each ``[`` body is a *straight-line* ``+-><``-only block (no
# brackets), and the closing ``]`` is a phantom character whose position is
# encoded so that the ``[``-fire seek finds it at the right rotation state.
#
# A block is ``[ body ]`` at positions ``p``..``q`` where ``len(body)``
# satisfies ``len(body) + 1 ≡ 0 (mod 8)``:
#
# - skip path (cell == 0): the ``[`` fires, rotates once, seeks forward for
#   ``]`` at depth 1, and lands at ``q + 1`` with rotation state ``p + 1``;
# - body path (cell != 0): the body runs (straight-line, pointer starts and
#   ends on the tested cell, which stays nonzero), and at ``q`` the phantom
#   shows ``rot^len(body)(']')`` = ``'['`` (since ``len(body) ≡ 7``), which
#   does not fire on the nonzero cell, so it advances to ``q + 1`` with state
#   ``q + 1 ≡ p + 1 (mod 8)``.
#
# Both paths therefore re-converge at ``q + 1`` in the same rotation state,
# so the rest of the program can be encoded position-wise.  A body command at
# relative offset ``j`` must also satisfy ``rot^{-j}(cmd)`` not a bracket, so
# the ``[``-fire seek (at state ``p + 1``) sees no bracket inside the body.
#
# The generator is a branch-free minterm sum over an idempotent-zeroing
# indirection: each input bit ``b_i`` (cell ``i``) and its complement ``c_i``
# (cell ``n + i``, set to 1) guard blocks that count mismatches into cells
# ``mc_k``; one block per minterm then zeroes ``m_k`` (cell
# ``2n + 1 + 2**n + k``) iff ``mc_k != 0``, so ``m_k == 1`` exactly when the
# input is ``k``; and blocks guarded by the ``1``-rows accumulate into the
# result cell, which is printed as ``48 + r``.


def jaune(truth_table: str) -> str:
    """Build a Jaune program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    All ``n`` bits are read up front -- one ``v`` each (a digit character,
    ``ord-48``) -- and the tree then routes with ``?`` jumps: a node walks to
    the cell holding its bit and ``N?`` jumps to label ``N`` when that cell is
    nonzero, else falls through.  Each leaf prints its answer with ``^`` and
    jumps to a shared end label.  A subtree whose table slice is a constant
    collapses to a single leaf.

    Only the inputs the tree actually branches on get a cell of their own:
    a read is followed by ``>`` when its bit is needed later and left to be
    overwritten by the next read when it is not, so the kept bits sit in one
    contiguous block and the tree navigates a span as wide as the function's
    real dependencies.  A leaf then prints from the cell it is already
    standing on -- its parent's test cell, whose value it knows -- so the
    answer costs at most one ``+``/``-`` and no navigation at all.

    **Reading up front is what makes the input count constant.**  The reads
    used to sit *at* the nodes, so a folded tree skipped them: a constant
    table consumed no input at all while a parity table consumed every bit,
    making the program's stream consumption a function of its truth table.
    That is the one thing every generator here may not do -- the reads are
    the interface -- and Jaune escaped the contract test that sweeps for it
    only by not being registered in ``BY_FUNCTION``.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.boolean.helpers.best_input_order`),
    which the hoist is what enables: with every bit parked in its own cell,
    a node can test any of them.  Navigation costs one ``>``/``<`` per cell
    crossed, so an order pays for the folds it wins, and the search measures
    rather than assumes.
    """
    return best_input_order(truth_table, _jaune_ordered)


def _jaune_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Jaune program; see :func:`jaune`.

    Two things keep this cheap, and both come from the tree's shape being
    known before a line is emitted.

    **Inputs the tree never tests are clobbered rather than stored.**  The
    read contract asks that every input be *consumed*, not that every value
    be *kept*, so an input no node branches on is read into the cell the
    next read overwrites -- ``v`` without the following ``>``.  The tested
    bits then land in adjacent cells, so the tree navigates a block as wide
    as the function's real dependencies rather than one as wide as ``n``.  A
    constant table reads every input and stores none.

    **A leaf prints from the cell it is already standing on.**  It was
    reached by its parent's test, so the pointer is on that parent's cell
    and the value there is known -- 1 on the then-branch, 0 on the else --
    which makes the leaf one ``+``/``-`` and a ``^`` with no navigation at
    all.  Mutating a bit cell is safe because exactly one leaf runs per
    execution and it jumps straight to the end.

    The pointer's position on entry to a node is a function of its *level*
    alone, never of the path taken: both of a parent's branches leave the
    pointer on the parent's cell, so the navigation is computed per level
    instead of threaded through the branch history.
    """
    n = _validate_truth_table(truth_table)
    label = [1]

    def fresh() -> int:
        label[0] += 1
        return label[0]

    def move(frm: int, to: int) -> str:
        return ">" * (to - frm) if to >= frm else "<" * (frm - to)

    stored = stored_inputs(truth_table, perm)
    # Reads run in input order; only a stored input advances the pointer, so
    # the kept bits occupy a contiguous block from cell 0.
    cell_of: dict[int, int] = {}
    reads = ""
    slot = 0
    for i in range(n):
        reads += "v"
        if i in stored:
            cell_of[i] = slot
            slot += 1
            reads += ">"
    # A clobbered read leaves its value under the pointer, so the cell the
    # reads finish on is blank only when the last read advanced off it.  A
    # whole-table constant prints from there and needs it zero, so step once
    # more when the final read clobbered -- and the entry cell moves with it.
    scratch = slot
    if n and (n - 1) not in stored:
        reads += ">"
        scratch = slot + 1

    def leaf(value: str, held: int | None, end: int) -> str:
        want = int(value)
        have = 0 if held is None else held
        adjust = "+" * (want - have) if want >= have else "-" * (have - want)
        return adjust + "^" + f"+{end}?"

    def node(
        level: int, lo: int, hi: int, entry: int, held: int | None, end: int
    ) -> str:
        if level == n or len(set(truth_table[lo:hi])) == 1:
            return leaf(truth_table[lo], held, end)
        # A clobbered input has no cell to test.  Its bit cannot change the
        # answer, so the two halves of this span are value-identical and
        # descending into either one is the same function -- take the zero
        # half, which keeps the row span halving in step with the level.
        if perm[level] not in cell_of:
            return node(level + 1, lo, (lo + hi) // 2, entry, held, end)
        cell = cell_of[perm[level]]
        then_lbl = fresh()
        mid = (lo + hi) // 2
        then = node(level + 1, mid, hi, cell, 1, end)
        else_ = node(level + 1, lo, mid, cell, 0, end)
        return move(entry, cell) + f"{then_lbl}?{else_}{then_lbl}:{then}"

    end = fresh()
    return reads + node(0, 0, 2**n, scratch, None, end) + f"{end}:."


def jaune_multiply() -> str:
    """Build a Jaune program reading two decimal numbers and printing their product.

    The program reads decimal digits (most-significant first, one per input
    line) into the first operand until a ``*`` line, then digits into the
    second operand until a ``#`` line, and prints the product as a decimal
    number with no leading zeros.  The single construction handles *any*
    number of digits, so the generator takes no ``n`` parameter: multiplying
    is one function ``a * b``, and the operand lengths are a property of the
    input, not of the function (unlike a boolean truth table, where ``n``
    selects a different function space).

    Jaune is the language the multiply capability needs: its cells do not
    wrap (the author's JauneJS stores each cell as a JavaScript number with
    plain ``+=``/``-=``, and this interpreter uses Python ``int``), so each
    operand fits in a single cell with no digit-per-cell carry, and ``^``
    prints the current cell as a decimal number directly.  Each read loop
    runs on a dedicated always-one
    cell: the ``?``/``!`` jumps are conditional, so a cell permanently set to
    1 gives the loop-back jump an unconditional trigger (the sentinel check
    is the only exit).  A digit is folded into the operand with ``v+`` (read
    a digit and add it), ``#`` (copy the current cell to hold) and a run of
    nine ``&`` (add the hold cell), which multiplies the accumulated value by
    10; a sentinel is detected by adding its offset from a digit (``*`` is
    42, so ``6+`` zeroes it) and jumping on zero.  The product is then a
    repeated-addition loop over the second operand.  Cells 0/1/2/3/4 hold
    the first operand, the digit scratch, the second operand, the result,
    and the always-one trigger.
    """
    out: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        while pos < target:
            out.append(">")
            pos += 1
        while pos > target:
            out.append("<")
            pos -= 1

    def cmd(s: str) -> None:
        out.append(s)

    move(4)
    cmd("1+")  # cell 4 = 1: the unconditional loop-back trigger
    # read the first operand until '*': label 1 at cell 4
    cmd("1:")
    move(1)
    cmd("v")
    cmd("6+")  # '*' is 42, so ord-48 == -6; +6 zeroes it
    cmd("2!")  # a zero (the sentinel) exits to label 2
    cmd("6-")
    move(0)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(0)
    cmd("&")
    move(4)
    cmd("1?")  # always jump back to label 1
    cmd("2:")  # first operand done; the '*' was read at cell 1
    pos = 1
    move(4)
    # read the second operand until '#': label 4 at cell 4
    cmd("4:")
    move(1)
    cmd("v")
    cmd("13+")  # '#' is 35, so ord-48 == -13; +13 zeroes it
    cmd("3!")  # a zero (the sentinel) exits to label 3
    cmd("13-")
    move(2)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(2)
    cmd("&")
    move(4)
    cmd("4?")  # always jump back to label 4
    cmd("3:")  # second operand done; the '#' was read at cell 1
    pos = 1
    move(2)
    # multiply: while cell 2 != 0: cell 3 += cell 0; cell 2 -= 1
    cmd("5:")
    cmd("6!")
    move(0)
    cmd("#")
    move(3)
    cmd("&")
    move(2)
    cmd("1-")
    cmd("5?")
    cmd("6:")
    pos = 2
    move(3)
    cmd("^")
    cmd(".")
    return "".join(out)


def suffolk(truth_table: str) -> str:
    """Build a Suffolk program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Suffolk has no branch and no data-dependent jump, so this is a
    branch-free sum of minterms, run at ``limit=1`` (a single pass, one
    read per input -- the default 10-pass rerun would replay every ``,``
    with no more input left).  The only nonlinearity is ``!``, which
    computes ``max(0, cell + 1 - acc)``: with a preloaded 48-cell and
    ``acc = 48 + bit`` (one ``,`` read), it yields the complement
    ``1 - bit``; a second ``!`` from a zero cell complements again to
    recover ``bit``.  Summing ``n`` literals (complement when the row wants
    a 0, raw bit when it wants a 1) into ``acc`` and applying ``!`` to a
    zero cell gives ``max(0, 1 - sum)``, which is 1 only when every literal
    matches (an AND of that row's minterm) and 0 otherwise.  Every row's
    minterm cell is 0 except the one matching the actual inputs, so summing
    all of them plus a preloaded 49-cell into ``acc`` and printing
    (``.`` emits ``chr(acc - 1)``) prints ``48`` or ``49``.

    Constant tables need no reads at all: ``.`` prints ``chr(acc - 1)``, so
    the accumulator only has to hold 50 (all-ones, prints ``49``) or 49
    (all-zeros, prints ``48``) at the print.

    A table with more ones than zeros is evaluated from its **zero** rows
    and the answer inverted, which costs one minterm block per row less.
    Both polarities are built and the shorter returned, rather than counting
    rows: the two are not symmetric, since a complement literal sits at a
    nearer cell than a raw one and every ``>`` run is paid per unit.  The
    saving averages 5.1% over every table at ``n == 3`` and reaches 45% on
    the densest tables at ``n == 4``.  ``_maybe_complement`` is deliberately
    not used -- its all-ones case complements to *no* minterms, which the
    constant-table branch above already handles better.
    """
    n = _validate_truth_table(truth_table)

    def const(gap: int, value: int) -> str:
        """``(gap '>'s then '!') * value`` builds ``value`` at that cell.

        ``!`` resets the pointer to 0, so each repetition re-walks ``gap``
        steps out to the same cell before incrementing it.
        """
        return (">" * gap + "!") * value

    if len({*truth_table}) == 1:
        # A constant table needs no minterms, but the reads are the language's
        # interface: skipping them leaves the caller's bits unread on the input
        # stream.  Read each input into its own scratch cell and discard it.
        reads = "".join(
            const(2 + i, _ASCII_ZERO) + ">" * (2 + i) + "," + "!" for i in range(n)
        )
        return const(1, _ASCII_ONE + int(truth_table[0])) + reads + ">" + "<" + "."

    def evaluate(wanted: str, *, invert: bool) -> str:
        """Sum the minterms of the rows equal to ``wanted``, then print.

        With ``invert`` the sum answers the *complement* of the table, so
        the print stage has to flip it back.
        """
        # Cell 1 holds the print stage's additive constant.  ``const``
        # re-walks the gap once per unit, so this has to live at the
        # cheapest cell there is: 49 units at cell 1 costs 98 characters,
        # where the same constant out past the minterm cells would cost
        # several hundred and swamp what the complement saves.
        body = const(1, _ASCII_ONE)
        # cells 2..2+n-1: complement of each input bit (1 - bit)
        for i in range(n):
            gap = 2 + i
            body += const(gap, _ASCII_ZERO) + ">" * gap + "," + "!"
        # cells 2+n..2+2n-1: the raw bit, recovered from the complement
        for i in range(n):
            gap = 2 + i
            raw_gap = 2 + n + i
            body += ">" * gap + "<" + ">" * raw_gap + "!"

        cells: list[int] = []
        next_cell = 2 + 2 * n
        for row in range(2**n):
            if truth_table[row] != wanted:
                continue
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            literals = [(2 + i) if v else (2 + n + i) for i, v in enumerate(bits)]
            body += "".join(">" * c + "<" for c in literals)
            body += ">" * next_cell + "!"
            cells.append(next_cell)
            next_cell += 1

        if not invert:
            body += "".join(">" * c + "<" for c in cells)
            body += ">" + "<"  # add the constant cell
            return body + "."
        # ``S`` is 1 exactly when the inputs match a row the table sends to
        # ``0``, so the answer is ``1 - S``.  ``.`` prints ``chr(acc - 1)``
        # and ``!`` computes ``max(0, cell + 1 - acc)``, so a cell preloaded
        # with 49 and hit with ``acc = S`` holds ``50 - S``; reading it back
        # makes ``acc = 50 - S`` and the print emits ``chr(49 - S)``.  The
        # clamp never bites, since ``S`` is 0 or 1.
        # ``S`` is 1 exactly when the inputs match a row the table sends
        # to ``0``, so the answer is ``1 - S``.  ``!`` computes
        # ``max(0, cell + 1 - acc)``, so cell 1's 49 becomes ``50 - S``;
        # reading it back makes ``acc = 50 - S`` and ``.`` (which emits
        # ``chr(acc - 1)``) prints ``chr(49 - S)`` -- ``'1'`` for S == 0 and
        # ``'0'`` for S == 1.  The clamp never bites, since ``S`` is 0 or 1.
        # Preloading 48 instead is the off-by-one that prints ``'/'``: the
        # print's ``- 1`` and ``!``'s ``+ 1`` both have to be counted.
        body += "".join(">" * c + "<" for c in cells)
        body += ">" + "!"
        body += ">" + "<"
        return body + "."

    plain = evaluate("1", invert=False)
    flipped = evaluate("0", invert=True)
    return min(plain, flipped, key=len)
