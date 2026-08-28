r"""Boolean-function generators via input-by-substitution.

A normal boolean generator produces one program that *reads* its inputs.
Some languages have no input mechanism but still have enough computation
power (output, constant construction, and a value-testable branch) to
evaluate a boolean function from *embedded* constants.  For those, a
parameterized generator emits a **template** with ``{X0}``.. placeholders
for the input bits; :func:`instantiate` replaces each placeholder with the
language's code that sets that input cell to the bit value.  The harness
instantiates the template once per input and runs it, so the program is a
decision tree over constants rather than a reader of input.

This is a separate class from the input-reading generators: it is useful
exactly for the no-input languages, and it does not make them read input —
the harness performs the injection.  :func:`bio` replaces ``{Xi}`` with an
increment that loads the raw bit into a register; :func:`back` replaces
``{Xi}`` with a ``\\`` or ``/`` mirror so the beam is reflected toward the
correct subtree; :func:`nocomment` replaces ``{Xi}`` with a constant-length
tape setter (``c``/``i``) and routes a decision tree with the ``s`` skip
(a runtime prologue computes each bit's complement via ``s``-as-NOT-gate,
so no ``{Ci}`` is needed); :func:`bitdeque`, :func:`ram0`, and
:func:`minsky_swap` replace ``{Xi}`` with fixed-length setters and route a
``POP``/``GOTO``, ``C``/``goto``, or ``~`` decision tree.

**Every input must be embedded exactly once.**  An input-capable language
reads each of its ``n`` inputs exactly once per run; a no-input language's
parameterized generator should match that, so a template may contain each
``{Xi}`` placeholder at most once.  Re-embedding a bit at multiple decision
nodes would let a no-input program "read" an input more than its
input-capable counterpart does, which muddies the generator API.  Each
generator below therefore stores every input once (a tape load, a register
pack, a deque/stack push, a variable, or a mirror) and reads it back, rather
than re-substituting it.

There is no complement placeholder.  :func:`instantiate` used to fill a
``{Ci}`` beside each ``{Xi}``, for a generator that wanted ``1 - bit``
embedded as a constant, but none does: ``bfpda``'s node structure needs a
truthy marker to stay on the stack after each bit is consumed, and the
marker's value never depends on the bit, so it is a constant written
straight into the template; ``nocomment`` computes each bit's complement
from ``{Xi}`` at runtime with its ``s``-as-NOT-gate.  The placeholder and
the ``set_comp`` argument that filled it are gone.
"""

from typing import TypeAlias

# Re-exported so this module stays the import site for the whole
# parameterized family; each of these owns a file because its
# construction (a search or a grid layout) dwarfs the others.
from esolangs.tools.boolean.a_painter_ant import a_painter_ant
from esolangs.tools.boolean.cod import cod
from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    decision_tree_tokens,
    instantiate,
)
from esolangs.tools.boolean.wii2d import wii2d

__all__ = [
    "a_painter_ant",
    "arrowqueue",
    "back",
    "bfpda",
    "bio",
    "bitdeque",
    "cod",
    "eval",
    "instantiate",
    "lamfunc",
    "minsky_swap",
    "nocomment",
    "ram0",
    "wii2d",
]

# A decision-tree node: ("leaf", leaf_id, value, None, None) or
# ("node", node_id, level, zero_subtree, one_subtree).
_Node: TypeAlias = "tuple[str, int, int, _Node | None, _Node | None]"


def bio(truth_table: str) -> str:
    """Build a BIO template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BIO has three registers (``x``, ``y``, ``z``) and no absolute jumps —
    its ``{``/``}`` loops are structurally matched — so the setter's length
    is unconstrained.  Each input is embedded once by packing it into ``x``:
    ``{Xi}`` becomes ``0ox`` repeated by the input's binary weight (``2**w``)
    for a one bit, so ``x = sum 2**w_i * bit_i`` is the input's numeric
    index.  A zero writes the same count to ``z`` instead, which nothing
    reads, so the two bits embed at equal width rather than a zero
    embedding as nothing.

    ``y`` is initialized to the table's first entry (``table[0]``), then
    ``2**n - 1`` *nested* loops each decrement ``x`` once (``0ix{ 1ox; ... };``)
    and, on the transition ``table[j-1] -> table[j]``, adjust ``y``: ``0oy``
    for a 0-to-1 rise, ``1oy`` for a 1-to-0 fall, nothing for a flat edge.
    The j-th level fires iff ``x >= j``, so for the packed value ``V`` the
    ops telescope to ``y = table[0] + sum_{j=1}^{V} (table[j] - table[j-1]) =
    table[V]``.  The result is printed with ``1iy``.
    """
    n = _validate_truth_table(truth_table)

    def yop(a: str, b: str) -> str:
        if a == b:
            return ""
        return "0oy;" if a == "0" else "1oy;"

    pack = " ".join("{X" + str(i) + "}" for i in range(n))
    inner = ""
    for j in range(2**n - 1, 0, -1):
        body = "1ox;" + yop(truth_table[j - 1], truth_table[j]) + inner
        inner = "0ix{" + body + "};"
    init = "0oy;" if truth_table[0] == "1" else ""
    return pack + " " + init + inner + "0oy;" * _ASCII_ZERO + "1iy;"


def eval(truth_table: str) -> str:  # noqa: A001 - the language is named "Eval"
    """Build an Eval template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Eval has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a bit push and the harness
    instantiates one program per input combination.  Each is two characters
    wide whichever bit it carries, so the program's shape does not reveal
    its inputs: the bit is staged on the tree stack, where ```` ` ````
    (``1 - ptr``) pushes a one and ``0`` pushes a zero, and ``=`` then moves
    it to the input stack the nodes read.  The tree is stored as a flat, full
    binary tree in heap (BFS) order on the tree stack; a node at index
    ``i`` tests the next input and the heap layout pins its two children at
    fixed offsets.

    A node is ``~=~?`` followed by ``i+1`` semicolons and a ``!``: ``~``
    switches to the input stack, ``=`` moves the top input onto the tree
    stack, ``~`` switches back, and ``?`` pops it -- skipping the next
    command when it is zero.  The ``;``s discard ``i+1`` elements when the
    bit is one (the skip makes it ``i`` when zero), so ``!`` pops the
    0-child (heap index ``2i+1``) for a zero bit and the 1-child (``2i+2``)
    for a one.  A leaf is ``0+.`` (prints 1) or ``0.`` (prints 0).  The
    template pushes the tree in BFS order, reverses the stack so the root
    is on top, and ``!`` evaluates it; each path keeps popping bits until a
    leaf prints.  No node or leaf contains a quote or backtick, so the
    strings need no escaping and the tree grows to any ``n``.

    A node whose rows all agree becomes the leaf it would have reached, and
    its descendants become empty strings.  The fold has to work that way
    round: the heap is *positional*, so the ``;`` run is a function of the
    node's own index and every child sits at a pinned ``2i+1``/``2i+2``, and
    deleting a subtree the way a token-stream generator does would shift
    every later index and misroute the whole tree.  Emptying the slots
    instead leaves the arithmetic untouched, and an emptied slot is never
    popped because the only node that routed into it has become a leaf.  A
    constant table goes from 127 to 47 characters at ``n == 3``.
    """
    n = _validate_truth_table(truth_table)

    def combo(leaf: int) -> tuple[int, ...]:
        """Input bits (most significant first) reaching the heap ``leaf``."""
        path: list[int] = []
        while leaf > 0:
            path.append(0 if leaf % 2 else 1)  # odd = left child = 0 branch
            leaf = (leaf - 1) // 2
        return tuple(reversed(path))

    def rows_under(i: int) -> list[int]:
        """Table rows reachable from heap node ``i``."""
        if i >= 2**n - 1:
            return [sum(b << (n - 1 - k) for k, b in enumerate(combo(i)))]
        return rows_under(2 * i + 1) + rows_under(2 * i + 2)

    # A node whose rows all agree is replaced, *in its own slot*, by the leaf
    # it would have reached.  The heap is positional -- every node's children
    # are pinned at 2i+1/2i+2 and its own ``;`` run is a function of ``i`` --
    # so a folded subtree cannot be deleted the way a token-stream tree's
    # can, or every later index would shift.  Leaving the slots in place and
    # emptying them keeps all of that arithmetic untouched: an empty string
    # is never popped, because the only node that routed into it is gone.
    dead: set[int] = set()
    tree: list[str] = []
    for i in range(2 ** (n + 1) - 1):
        if i in dead:
            tree.append("")
            continue
        rows = rows_under(i)
        values = {truth_table[row] for row in rows}
        if i < 2**n - 1 and len(values) == 1:
            tree.append("0+." if values.pop() == "1" else "0.")
            below = [2 * i + 1, 2 * i + 2]
            while below:  # the whole subtree, not just the two children
                child = below.pop()
                dead.add(child)
                if child < 2**n - 1:
                    below += [2 * child + 1, 2 * child + 2]
        elif i < 2**n - 1:  # internal node: test the next input
            tree.append("~=~?" + ";" * (i + 1) + "!")
        else:  # leaf: print the table entry for this path
            tree.append("0+." if truth_table[rows[0]] == "1" else "0.")

    bits = "".join("{X" + str(i) + "}" for i in range(n - 1, -1, -1))
    return bits + "".join(f'"{t}"' for t in tree) + "*!"


def back(truth_table: str) -> str:
    r"""Build a Back template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Back is a no-input grid language: a beam travels the grid and ``-`` flips
    the current tape bit, ``+`` steps the beam forward when the current bit
    is 0, ``<``/``>`` move the tape pointer, ``\`` reflects the beam down,
    and ``*`` halts printing the tape.  Each input is embedded once by
    filling its tape cell over two load rows: a constant ``-`` primes the
    cell to 1 for either bit, then ``{Xi}`` finishes it -- ``+`` (inert on
    a set cell) for a one, ``-`` (flipping it back) for a zero.  So cells
    ``0..n-1`` hold the inputs and cell ``n`` is the answer cell.  Both
    bits cost the same two rows and, because no ``+`` ever meets a zero
    cell here, both rows run for either bit.  A zero used to embed as a
    blank the rstrip then removed, which made the program's height reveal
    it.

    A decision node is ``+\>``: ``+`` tests the current tape bit (advancing
    the beam straight past the ``\`` when it is 0) and ``\`` reflects the
    beam down when it is 1, while ``>`` advances the tape pointer to the next
    input.  Both branches advance the pointer once, so a leaf at depth ``d``
    has the pointer at cell ``d``.  A leaf walks to cell ``n``, flips it with
    ``-`` when its value is 1, and halts.

    The load runs *down column 0* and the tree starts at column 1, so no row
    carries the load's width as indent.  A ``/`` at the origin does both
    turns: the beam starts heading right, the ``/`` sends it up and off the
    top edge onto the bottom row, it runs the load upward back to the origin,
    and the ``/`` -- now taking a beam heading up -- turns it right into the
    tree.  The load is therefore written bottom-to-top, and the tree is free
    to begin one column in.

    The answer is therefore the *value* of cell ``n``, which the halt dump
    prints, rather than the head's position, which it does not.  An earlier
    layout kept a 0-cell and a 1-cell and parked the head on whichever
    matched; that made the result unreadable from the program's own output,
    so Back could have no committed example and its generator tests had to
    reimplement the language to find the head.  One answer cell costs
    nothing -- a leaf spends one ``-`` instead of one extra pointer move --
    and makes the dump self-describing.
    """
    n = _validate_truth_table(truth_table)

    # The load: fill cells 0..n-1 with the inputs, then '>' to open the answer
    # cell at n and n '<' to walk the pointer back to cell 0 for the tree's
    # first test.  Held as units because a '{Xi}' is one grid cell but four
    # template characters.
    units: list[str] = []
    for i in range(n):
        # Two units per input, so neither bit has to be written as a blank:
        # the beam reads one cell per row in column 0, so the setter's second
        # command needs a row of its own rather than the column beside it.
        # Where the tree is the taller of the two these rows already exist.
        #
        # The first row is a constant '-' that primes the cell to 1 for both
        # bits alike, and the *second* carries the placeholder that finishes
        # it: '-' again to flip a zero back down, '+' to leave a one standing.
        # Putting the bit on the trailing row rather than the leading one is
        # what makes every load row execute -- see the fill for why the older
        # '{Xi}' + '+' order skipped a row instead.
        units.append("-")
        units.append("{X" + str(i) + "}")
        if i < n - 1:
            units.append(">")
    units.append(">")
    units.extend("<" * n)

    # The load occupies column 0 and the tree everything from column 1, so the
    # tree carries no indent for it -- the drawing's width is the tree's alone.
    # A single '/' at the origin performs both turns.  The beam starts at (0,0)
    # heading right; the '/' turns it up, off the top edge and onto the bottom
    # row, where it runs the load *upward* back to the origin; the '/' takes it
    # a second time, now heading up, and turns it right into the tree.  So the
    # load is written bottom-to-top, and an earlier layout's two '\' -- one to
    # drop the beam off the load's end, one to turn it back right -- are both
    # gone along with the row and the indent they cost.
    #
    # Riding off the top edge makes the grid's toroidal wrap load-bearing:
    # ``_Machine.step`` advances with ``% len(code)``, so up from row 0 lands
    # on the last row.  The wiki text the interpreter quotes does not mention
    # the edges at all, and no interpreter test covers a wrap, so this is the
    # one place the generator leans on behaviour with no witness outside this
    # repo's own interpreter.
    grid: dict[tuple[int, int], str] = {}
    next_row = [1]

    def leaf(level: int, value: str, row: int, col: int) -> None:
        # walk to the single answer cell, write a 1 there when the leaf's
        # value is 1 (it starts 0), and halt
        delta = n - level
        move = (">" if delta >= 0 else "<") * abs(delta)
        code = move + ("-" if value == "1" else "") + "*"
        for k, ch in enumerate(code):
            grid[(row, col + k)] = ch

    def emit(level: int, lo: int, hi: int, row: int, col: int) -> None:
        vals = {truth_table[r] for r in range(lo, hi)}
        if level == n or len(vals) == 1:
            leaf(level, vals.pop() if level < n else truth_table[lo], row, col)
            return
        mid = lo + (hi - lo) // 2
        grid[(row, col)] = "+"
        grid[(row, col + 1)] = "\\"
        grid[(row, col + 2)] = ">"
        emit(level + 1, lo, mid, row, col + 3)  # zero (bit=0) straight
        nrow = next_row[0]
        next_row[0] += 1
        grid[(nrow, col + 1)] = "\\"
        grid[(nrow, col + 2)] = ">"
        emit(level + 1, mid, hi, nrow, col + 3)  # one (bit=1) child

    emit(0, 0, 2**n, 0, 1)  # tree root at column 1, the beam arriving rightward

    # The grid is as tall as whichever of the two needs more rows: the tree
    # wants 2**n and the load wants one row per unit below the '/'.  Past
    # n = 3 the tree is the taller of the two, so the load's rows start
    # sharing with tree rows -- which is safe for the same reason the whole
    # template is: a '{Xi}' is the only thing on its row that instantiation
    # resizes, it always shrinks by exactly three (every embedding is one
    # character, for either bit value), and it sits left of the tree, so the
    # tree glyphs on that row slide back to the columns they were drawn for.
    # An embedding whose width depended on the bit would break that silently.
    height = max(max(r for r, _ in grid) + 1, 1 + len(units))
    width = max(c for _, c in grid) + 1
    rows = [[" "] * width for _ in range(height)]
    for (r, c), ch in grid.items():
        rows[r][c] = ch
    rows[0][0] = "/"
    for k, unit in enumerate(units):
        rows[height - 1 - k][0] = unit
    # Every row is built at the full grid width, so the rstrip trims the pad
    # each one carries past its last glyph.  It no longer has a bit to hide:
    # both bits embed as a single command ('-' or '+'), never as the blank a
    # zero once used, so no placeholder row instantiates to whitespace and
    # the strip cannot change a filled row's length.
    return "\n".join("".join(row).rstrip() for row in rows)


def nocomment(truth_table: str) -> str:
    """Build a NoComment template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    NoComment has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a constant-length setter for each
    input bit, and the harness instantiates one program per input
    combination.  Unlike an earlier version of this generator, the
    complement is *not* embedded: NoComment's ``s`` (skip the next block iff
    the tested cell is nonzero) doubles as a NOT gate, because the skipped
    block only runs when the cell is zero.  A short runtime prologue pushes
    a fixed skip length, tests each raw bit cell, and increments a fresh
    complement cell in the skipped block -- so ``comp_i = 1 - bit_i`` is
    computed once per input from the embedded bit, with no ``{Ci}``
    placeholder and no second embed.

    Rather than routing a decision tree, the program **computes the input's
    numeric index** and uses it as a byte-sized ``s`` skip into a staircase of
    ``l`` moves that land the pointer on a pre-loaded output cell holding
    ``48 + truth_table[index]``.  Each bit ``i`` contributes its weight
    (``2**w``) to the index cell only when the bit is one -- the guard tests
    the complement cell so the contribution is skipped when the bit is zero.
    The output is then a single ``o``.

    This is a straight-line program: no leaf chains, no interleaved stations,
    no placement.  Every jump is byte-sized, so the index must fit a byte --
    the generator covers every table up to eight inputs and raises
    :class:`ValueError` beyond that.
    """
    n = _validate_truth_table(truth_table)
    if n > 8:
        raise ValueError("the NoComment boolean generator supports n <= 8")

    k = 2**n
    index = 2 * n
    skip_base = index + 1  # one skip cell per input bit
    tbase = skip_base + n  # the output cells
    sentinel = tbase + k  # non-zero cell the final ``s`` gates on
    scratch = sentinel + 1  # reused per bit to push each NOT gate's skip length

    # Emit the index computation and the output staircase.  Each bit's
    # guarded increment ends with the pointer back on its complement cell,
    # so the emitted moves stay consistent.
    commands: list[str] = []
    ptr = [index]

    def move(dst: int) -> None:
        while ptr[0] < dst:
            commands.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            commands.append("l")
            ptr[0] -= 1

    skip_vals: dict[int, int] = {}
    for i in range(n):
        w = n - 1 - i
        comp = n + i
        d = skip_base + i
        move(d)
        commands.append("n")
        move(comp)
        commands.append("s")
        block = len(commands)
        move(index)
        commands.extend(["i"] * (2**w))
        move(comp)
        skip_vals[d] = len(commands) - block
    move(index)
    commands.append("n")  # push the index
    ptr[0] = index
    move(sentinel)
    commands.append("s")  # skip by the index into the staircase
    commands.extend(["l"] * k)
    commands.append("o")

    # Setup: bits, complements, index, skip cells, output cells, sentinel,
    # scratch.  The complement cells (n..2n-1) start at zero and are filled
    # by the NOT-gate prologue below, not by a {Ci} placeholder.
    setup: list[str] = []
    setup_ptr = [0]

    def setup_move(dst: int) -> None:
        while setup_ptr[0] < dst:
            setup.append("r")
            setup_ptr[0] += 1
        while setup_ptr[0] > dst:
            setup.append("l")
            setup_ptr[0] -= 1

    for i in range(n):
        setup.append("{X" + str(i) + "}")
        setup.append("r")
    setup_ptr[0] = n

    # NOT-gate prologue: for each bit i, comp_i = 1 - bit_i.  ``s`` at the
    # bit cell skips a fixed-length block (move to comp_i, set it, move back)
    # exactly when the bit is nonzero, so the block runs -- and increments
    # the complement cell -- only when the bit is zero.  Both the skip and
    # fall-through paths leave the pointer back on the bit cell, so the
    # next bit's prologue starts from a known position.
    for i in range(n):
        comp = n + i
        # comp is always to the right of bit i (comp - i == n), so the gate
        # is a straight-line move-set-return with no branching to track.
        dist = comp - i
        gate = ["r"] * dist + ["i"] + ["l"] * dist
        gate_len = len(gate)

        setup_move(scratch)
        setup.append("c")
        setup.extend(["i"] * gate_len)
        setup.append("n")  # push gate_len
        setup_move(i)
        setup.append("s")
        setup.extend(gate)

    setup_move(index)
    setup.append("c")  # index starts at zero
    cells: list[tuple[int, int]] = list(skip_vals.items())
    cells.append((sentinel, _ASCII_ZERO))
    for j in range(k):
        cells.append((tbase + j, _ASCII_ZERO + int(truth_table[j])))
    cells.sort(key=lambda cv: cv[1])
    if cells:
        first_addr, first_value = cells[0]
        setup_move(first_addr)
        setup.extend(["i"] * first_value)
        prev_value = first_value
        for addr, value in cells[1:]:
            setup.append("n")
            setup_move(addr)
            setup.append("f")
            diff = value - prev_value
            setup.extend(["i"] * diff if diff > 0 else ["d"] * -diff)
            prev_value = value
    setup_move(index)

    return "".join(setup + commands)


def bfpda(truth_table: str) -> str:
    """Build a BF-PDA template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BF-PDA has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a push of the bit, four
    characters wide whichever bit it is, so the program's shape does not
    reveal its inputs.  The harness instantiates one program per input
    combination.  Each input is embedded once: the load phase pushes every
    ``<@{Xi}`` pair (a constant 1 marker, then the bit) up front, so the
    stack holds all ``n`` bits and markers with ``b0`` on top.

    Every character outside ``@.<>[]`` is a comment, so the commands are
    emitted unseparated; the fragments below are spaced only to read.

    A node tests its bit and *consumes* it for the next level using a
    ``<``-break loop ``[ > one < ] > [ > zero < ] >``: ``[`` enters when the
    bit is one, ``>`` pops it, the one-branch pops the marker (to expose the
    next bit), and ``<`` pushes a fresh zero to break the loop -- which
    works because the guard was already popped, unlike ``[ sub @ ]`` where
    ``@`` needs the guard still on top.  The zero-branch is selected by the
    second loop testing the marker: when the bit is zero, ``[`` never
    entered, so the outer ``>`` pops the *bit* instead (it was never
    consumed), exposing the marker as the new top.  The marker's role is
    only to be truthy there -- its value never depends on the input, so a
    constant 1 (not the input's complement) is correct, and it is embedded
    directly in the template rather than through the bit-value substitution.
    A leaf pops the remaining pre-loaded bits (``2*(n-level)`` of them) and
    prints the constant answer.
    """
    n = _validate_truth_table(truth_table)

    # load: push a constant-1 marker then the bit, so top = b0
    head = "".join("<@{X" + str(i) + "}" for i in range(n - 1, -1, -1))

    def leaf(level: int, value: str) -> str:
        # consume the remaining pre-loaded bits, then print the answer
        return ">" * (2 * (n - level)) + ("<@" if value == "1" else "<") + ".>"

    # Not routed through :func:`decision_tree_tokens`: this tree is a plain
    # string with no index to thread, so the walker's token lists would have
    # to be one-element lists unwrapped at every use, which reads worse than
    # the four lines it saves.
    def node(i: int, rows: list[int]) -> str:
        results = {truth_table[r] for r in rows}
        if i == n or len(results) == 1:
            return leaf(i, results.pop() if i < n else truth_table[rows[0]])
        zero = [r for r in rows if ((r >> (n - 1 - i)) & 1) == 0]
        one = [r for r in rows if ((r >> (n - 1 - i)) & 1) == 1]
        sub0 = node(i + 1, zero)
        sub1 = node(i + 1, one)
        # one-branch pops ~bi first (expose next bit); zero-branch has it popped
        # by the node's own loop
        return "[>" + ">" + sub1 + "<]>[>" + sub0 + "<]>"

    return head + node(0, list(range(2**n)))


def lamfunc(truth_table: str) -> str:
    """Build a Lamfunc template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Lamfunc has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become the binary literal for each input
    bit, and the harness instantiates one program per input combination.

    Each input is stored once in a variable (``vs v{i} {Xi}``), so the inputs
    are embedded exactly ``n`` times; the decision tree then reads each bit
    back with ``vg v{i}`` instead of re-embedding it at every node.  The tree
    is a chain of ``i`` builtins — ``i x y z`` returns ``y`` when ``x`` is
    nonzero else ``z`` — with ``p 0``/``p 1`` at the leaves printing the
    table's result as binary.  A subtree whose table slice is a constant
    collapses to a single leaf, so constant rows emit no branching.
    """
    n = _validate_truth_table(truth_table)

    def node(level: int, lo: int, hi: int) -> str:
        results = {truth_table[k] for k in range(lo, hi)}
        if level == n or len(results) == 1:
            return f"p {results.pop()}"
        mid = (lo + hi) // 2
        # i x y z returns y when x is nonzero else z: y is the one-case
        return f"i vg v{level} {node(level + 1, mid, hi)} {node(level + 1, lo, mid)}"

    head = " ".join(f"vs v{i} {{X{i}}}" for i in range(n))
    return head + " " + node(0, 0, 2**n)


def bitdeque(truth_table: str) -> str:
    """Build a Bitdeque template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Bitdeque has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a *fixed-length* two-command
    setter per bit, and the harness instantiates one program per input
    combination.  The earlier wall said the absolute ``GOTO N`` targets shift
    because the setter had variable length (``INVERT`` vs nothing); the fixed
    setter removes that: each bit is pushed as exactly ``INVERT PUSH`` when
    it differs from the register and ``PUSH INVERT`` when it matches, and
    the register flips after every block, so the load is always ``2n``
    commands and no absolute index moves between instantiations.

    Bits are pushed in reverse order so ``POP`` (LIFO) yields the most
    significant bit first, matching the contiguous MSB-first decision-tree
    splits.  A node pops one bit and ``GOTO``s to the one-subtree when it is
    one, with the zero-subtree falling through in place.  A leaf drains the
    deque with ``n+1`` ``POP``s (so the register is exactly zero even for a
    collapsed tree), pushes the answer, forces the register back to one with
    a trailing ``INVERT``, and ``GOTO``s past the program end to halt -- so
    every leaf always routes and the deque printed at halt holds exactly the
    answer.
    """
    n = _validate_truth_table(truth_table)

    def leaf(answer: str) -> list[str]:
        out = ["POP"] * (n + 1)
        if answer == "1":
            out.append("INVERT")
        out.append("PUSH")
        if answer == "0":
            out.append("INVERT")
        out.append("GOTO@END")
        return out

    # the load block, most significant placeholder first (so the first POP
    # after the load is the MSB); each placeholder expands to two commands
    head = ["{X" + str(i) + "}" for i in range(n - 1, -1, -1)]

    # A node spends ``POP`` and its ``GOTO`` before either subtree, so the
    # walker's ``at`` lands on this node and ``at + 2`` on the zero subtree.
    # The load block occupies ``2n`` commands ahead of the tree, which is
    # where the indices start, so the ``GOTO`` operands are right after
    # substitution.
    tree = decision_tree_tokens(
        truth_table,
        lambda _level, row: leaf(truth_table[row]),
        lambda _level, zero, one, at: [
            "POP",
            f"GOTO {at + 2 + len(zero)}",
            *zero,
            *one,
        ],
        parent_width=2,
        start=2 * n,
        collapse=True,
    )
    end = 2 * n + len(tree)
    return " ".join(head + ["GOTO " + str(end) if t == "GOTO@END" else t for t in tree])


def _ram0_width(level: int) -> int:
    """Commands a RAM0 tree node spends before its subtrees.

    ``Z``, an ``A`` per level (the cell address), ``L``, ``C``, and the
    ``goto`` that reaches the one-subtree -- so the width grows with depth,
    which is why the walker takes a callable rather than a constant.
    """
    return level + 4


def ram0(truth_table: str) -> str:
    """Build a RAM0 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    RAM0 has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a fixed-length two-command
    setter — ``Z Z`` for a zero, ``Z A`` for a one — independent of the
    incoming register (``Z`` resets absolutely).  The earlier wall's
    variable-length setter (``Z`` vs ``Z A``) was what shifted the absolute
    ``goto`` operands; the padded setter removes that.

    A load phase stores each bit once in its own RAM cell (address ``i``),
    so the inputs are embedded exactly ``n`` times; the decision tree then
    *loads* each bit with RAM0's indirect ``L`` (``z := ram[z]``) rather than
    re-embedding it, so the tree nodes contain no substitution.  Each node
    sets ``z`` to its address, loads the bit, and ``C`` skips the following
    ``goto`` when ``z`` is zero (the zero-subtree falls through in place)
    while the ``goto`` jumps to the one-subtree otherwise.  A leaf sets
    ``z`` to the answer and uses RAM0's *unconditional* ``goto`` to run off
    the program end, so the final ``z`` read from the state dump is the
    answer.
    """
    n = _validate_truth_table(truth_table)

    tokens: list[str] = []
    pos = 0  # instantiated command index of the next command

    # load phase: ram[i] = bit i, embedded exactly once each
    for i in range(n):
        tokens.append("Z")
        tokens.extend("A" for _ in range(i))
        tokens.append("N")
        pos += 1 + i + 1
        tokens.append("{X" + str(i) + "}")  # expands to "Z A" / "Z Z"
        pos += 2
        tokens.append("S")
        pos += 1

    def leaf_tokens(_level: int, row: int) -> list[str]:
        return ["Z", "A" if truth_table[row] == "1" else "Z", "END@"]

    def node(level: int, zero: list[str], one: list[str], at: int) -> list[str]:
        # ``Z``, the level's ``A`` run, ``L``, ``C`` and the ``ONE@`` slot all
        # precede the subtrees, which is the node's own width; the one subtree
        # therefore starts a further ``len(zero)`` along, 1-based.
        return [
            "Z",
            *("A" for _ in range(level)),
            "L",
            "C",
            f"ONE@{at + _ram0_width(level) + len(zero) + 1}",
            *zero,
            *one,
        ]

    # Every tree token is one command (unlike the load block's ``{Xi}``, which
    # expands to two), so the tree's command count is its token count.
    tree = decision_tree_tokens(
        truth_table,
        leaf_tokens,
        node,
        parent_width=_ram0_width,
        start=pos,
        collapse=True,
    )
    tokens += tree
    end = pos + len(tree) + 1  # 1-based goto operand just past the last command
    return " ".join(
        str(end) if t == "END@" else str(int(t[4:])) if t.startswith("ONE@") else t
        for t in tokens
    )


def minsky_swap(truth_table: str) -> str:
    """Build a Minsky Swap template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Minsky Swap has no input command, so this is a parameterized generator:
    the template's ``{Xi}`` placeholders become *fixed-length* setters that
    assemble the input's numeric index into ``reg[0]`` — one block per bit,
    so the inputs are embedded exactly ``n`` times.  Each non-LSB bit's block
    is ``2**n`` commands long: ``+`` repeated for its weight followed by
    ``*``-padding to length (both runs are even, so the pointer is restored),
    or ``*``-padding alone for a zero.  The LSB block is the length-4
    ``+*+*`` (adds one, and leaves ``reg[1]`` polluted with a one) or
    ``****`` (a no-op), so the setter length is fixed without an odd pad.

    A cascade of ``2**n`` ``~``s then routes the assembled value *v* to leaf
    *v* — each ``~`` decrements a nonzero register and jumps on zero, so the
    (v+1)-th one sees the value hit zero.  A leaf flips the polluted
    ``reg[1]`` (which holds the LSB) to the answer, then ``~``s on the
    (zeroed) ``reg[0]`` to run off the program end, so the dumped registers
    read ``0 {answer}``.
    """
    n = _validate_truth_table(truth_table)

    tokens: list[str] = []
    targets: list[int] = []
    pos = 0  # instantiated command index of the next command

    # load: bits MSB first; every non-LSB setter is a length-2^n block, the
    # LSB a length-4 block
    for i in range(n - 1):
        tokens.append("{X" + str(i) + "}")
        pos += 2**n
    tokens.append("{X" + str(n - 1) + "}")
    pos += 4

    for _ in range(2**n):  # cascade: route the assembled value to leaf v
        tokens.append("~")
        targets.append(0)
        pos += 1
    for v in range(2**n):  # leaves: reg[1] holds the LSB; make it the answer
        targets[v] = pos + 1
        tokens.append("*")  # pointer onto reg[1]
        pos += 1
        lsb = v & 1
        if lsb == 1 and truth_table[v] == "0":
            tokens.append("~")  # reg[1] is 1 here, so it decrements, no jump
            targets.append(0)
            pos += 1
        elif lsb == 0 and truth_table[v] == "1":
            tokens.append("+")
            pos += 1
        tokens.append("*")  # pointer back onto reg[0]
        pos += 1
        tokens.append("~")  # reg[0] is 0, so this always jumps to the end
        targets.append(0)
        pos += 1

    end = pos + 1  # 1-based target just past the last command
    return (
        " ".join(tokens) + "\n" + " ".join(str(end if t == 0 else t) for t in targets)
    )


# --- ArrowQueue (no-input grid language; parameterized + termination convention) ---
#
# Boolean generator for ArrowQueue.
#
# ArrowQueue is a 2D grid language with a queue: ``*`` turns the pointer
# clockwise, ``~`` pushes the current direction onto the queue, and ``+``
# pops the queue and points the pointer in the popped direction (halting on
# an empty pop).  It has no input and no output, so the generator follows
# the parameterized convention (like ``bitdeque``/``minsky_swap``) AND the
# termination convention (like ``point_break``): the template carries
# ``{Xi}`` placeholders for the input bits, :func:`_instantiate_arrowqueue`
# fills each with the language's per-bit embedding, and the result is read
# from whether the instantiated program *halts* (a ``0`` table entry) or
# *loops forever* (a ``1`` entry) -- the same convention as the committed
# halt-vs-hang ring (see ``docs/walls.md``).
#
# The template is a grid:
#
# - the first rows embed each input once, one ``{Xi}`` placeholder per bit
#   (the queue stores bits as directions: right is 0, down is 1);
# - the next rows queue the right/down/left/up loop components (a ``0``
#   leaf pops them all and then halts on the empty pop; a ``1`` leaf's ring
#   sustains on them);
# - the decision tree then pops each bit at a ``+`` branch and routes the
#   pointer right for a 0 bit or down for a 1 bit.  A ``0`` leaf is empty,
#   so the pointer runs off the grid and halts; a ``1`` leaf is a ring that
#   pushes on every edge and pops on every corner, sustaining forever.
#
# The tree is a full binary tree built from 3x3 blocks: a 0-branch
# (``" + "``) pops the next bit, sending the pointer right for 0 and down
# for 1; a 1-branch (``"*  "``/``"** "``) reflects the down-route back to
# the right; and each leaf is a 3x3 output block.  Connecting two subtrees
# places a 0-branch at the top-left, the first subtree at its right exit,
# the second at the 1-branch's right exit, and the 1-branch at the bottom
# left (one row below the first subtree), filling the rest with spaces.
# The pointer enters the whole tree by descending column 1 from the loop
# section, which pops the top-left 0-branch's ``+`` directly.

_TREE_1 = ["+~+", "~ ~", "+~+"]  # the ``1`` leaf: a self-sustaining ring
_TREE_0 = ["   ", "   ", "   "]  # the ``0`` leaf: empty, runs off-grid to halt
_TREE_BRANCH_0 = [" + ", "   ", "   "]  # pops a bit; 0 goes right, 1 goes down
_TREE_BRANCH_1 = ["*  ", "** ", "   "]  # reflects the down-route back to the right

# Input-embedding blocks.  A ``1`` bit pushes down (1) and a ``0`` bit pushes
# right (0).  The first block is one row taller: the pointer enters it
# heading right from the top-left corner and the ``*`` turns it down onto
# the ``~``, while every later block is entered heading down from the
# previous block's exit (each block leaves the pointer heading down at
# column 3, one row below itself).
# A one bit's block used to be its ``~`` and nothing else, where a zero
# bit's is a dense box, so ``_compact`` dropped the one's blank rows and the
# emitted program's size counted the ones: at n == 2 the four programs came
# out 123, 110, 110, and 97 characters.  The one blocks now carry inert
# walls sized so each block's glyphs occupy the same number of characters as
# the zero block it stands against (18 for the first, 14 for the rest).
#
# What a row costs is ``len(row.rstrip())``, so what matters is the column
# its *last* glyph sits in -- a row needs one wall, not a run of them, and
# the blanks to its left are paid for either way.  That holds for the ``~``
# rows too: leading blanks hold the ``~`` at column 3 just as well as glyphs
# would, so the row is a bare ``~`` with one wall past it.
#
# ``*`` turns the IP clockwise, so a wall is only inert where the IP cannot
# reach it.  The IP enters the header at (0, 0) heading right and crosses
# columns 0-2 of that row to reach its ``*``, so the first block's row 0 is
# left exactly as it was; every cell walled here is one no run visits.
_FIRST_ONE = ["   *", "   ~*", "  *", "  *", "  *"]
_FIRST_ZERO = ["   *", "*~* ", "*  *", "*  *", "* * "]
_NEXT_ONE = ["   ~*", "  *", "  *", "  *"]
_NEXT_ZERO = ["*~* ", "*  *", "*  *", "* * "]

# The loop-component section: entered heading down at column 3 from the last
# embedding block, it queues right, down, left, and up (in that order, so
# the queue holds ``[bits..., R, D, L, U]`` at the tree) and routes the
# pointer down column 1 into the tree.
_MIDDLE = ["*~* ", "*  *", "*  *", "~ ~ ", "*~* ", "**  ", "*  *"]


def _header_rows(bits: list[int]) -> list[str]:
    """Build the input-embedding rows for ``bits`` (most significant first)."""
    rows = list(_FIRST_ONE if bits[0] else _FIRST_ZERO)
    for bit in bits[1:]:
        rows.extend(_NEXT_ONE if bit else _NEXT_ZERO)
    return rows


def _connect(t0: list[str], t1: list[str]) -> list[str]:
    """Connect two decision subtrees into one.

    Places a 0-branch at the top-left, ``t0`` at its right exit, a 1-branch
    at the bottom left (just below ``t0``, catching the down-route), and
    ``t1`` at the 1-branch's right exit; everything else is spaces.
    """
    yb = len(t0)  # the 1-branch's top row: one row below ``t0``
    width = max(3 + len(t0[0]), 3 + len(t1[0]))
    height = max(3, yb + 3, yb + len(t1))
    grid = [[" "] * width for _ in range(height)]
    for r, line in enumerate(_TREE_BRANCH_0):
        for c, ch in enumerate(line):
            grid[r][c] = ch
    for r, line in enumerate(_TREE_BRANCH_1):
        for c, ch in enumerate(line):
            grid[yb + r][c] = ch
    for r, line in enumerate(t0):
        for c, ch in enumerate(line):
            grid[r][3 + c] = ch
    for r, line in enumerate(t1):
        for c, ch in enumerate(line):
            grid[yb + r][3 + c] = ch
    return ["".join(row) for row in grid]


def _drained_leaf(value: str, skipped: int) -> list[str]:
    """Build a folded leaf that drains the ``skipped`` bits it never popped.

    Folding a constant subtree skips its ``+`` branches, which would leave
    those bits queued *ahead* of the four loop components.  A ``0`` leaf
    does not care -- it halts by running off the grid, and no queue content
    prevents that -- but a ``1`` leaf's ring pops a direction at each corner
    and needs to find exactly ``R, D, L, U``.

    So each skipped bit gets a drain: a ``+`` whose two exits reconverge on
    one cell.  Popping a ``0`` sends the IP right into a ``*`` that turns it
    down; popping a ``1`` sends it down around three ``*`` that walk it back
    up and right.  Both arrive at the same cell -- with *different* headings,
    which is fine, because a ``+`` pops on arrival regardless of direction.
    Chaining them steps one row down and one column right per bit::

         +*        the ``+`` pops a stale bit
        *  *       0 goes right then down, 1 goes down then round
        ** +*      both land on the next ``+``

    The drains push nothing, so the ring receives the queue it expects.
    """
    # The leaf is 3x3 placed at (skipped, skipped + 1), so the grid needs
    # ``skipped + 3`` rows and one more column than that.
    grid = [[" "] * (skipped + 4) for _ in range(skipped + 3)]
    for i in range(skipped):
        grid[i][i + 1] = "+"
        grid[i][i + 2] = "*"
        grid[i + 1][i] = "*"
        grid[i + 2][i] = "*"
        grid[i + 2][i + 1] = "*"
    leaf = _TREE_1 if value == "1" else _TREE_0
    for r, line in enumerate(leaf):
        for c, char in enumerate(line):
            if char != " ":
                grid[skipped + r][skipped + 1 + c] = char
    return ["".join(row) for row in grid]


def _tree(values: list[str]) -> list[str]:
    """Build the decision tree for the ``2**n`` table values.

    A subtree whose values all agree folds to a single leaf rather than the
    branches that would all reach it.  The slice's own length says how many
    bits the leaf must drain -- see :func:`_drained_leaf`, which is what
    lets a ``1`` leaf fold at all.
    """
    if len(set(values)) == 1:
        skipped = len(values).bit_length() - 1
        return _drained_leaf(values[0], skipped)
    if len(values) == 2:
        return _connect(
            _TREE_1 if values[0] == "1" else _TREE_0,
            _TREE_1 if values[1] == "1" else _TREE_0,
        )
    half = len(values) // 2
    return _connect(_tree(values[:half]), _tree(values[half:]))


def arrowqueue(truth_table: str) -> str:
    """Build an ArrowQueue template for an ``n``-input Boolean function.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ArrowQueue has no input command, so this is a parameterized generator:
    the returned template's ``{Xi}`` placeholders become the per-bit
    embedding blocks, and the harness instantiates one program per input
    combination (see :func:`_instantiate_arrowqueue`).  Since ArrowQueue has
    no output, the result is read from the termination convention: the
    instantiated program halts iff the table entry for the embedded bits is
    ``0`` and loops forever iff it is ``1``.

    The construction embeds each bit once in the header rows (a ``1`` bit
    pushes down, a ``0`` bit pushes right), queues the right/down/left/up
    loop components, and routes a decision tree by popping the bits at
    ``+`` branches.  Each leaf is a 3x3 block: a ``1`` entry is a
    self-sustaining ring and a ``0`` entry is empty (the pointer runs off
    the grid, which halts).

    A constant subtree folds to a single leaf, which drains the bits the
    skipped branches would have popped -- see :func:`_drained_leaf`.  A
    constant table is 128 characters against 275 at n == 3, and 130 against
    1434 at n == 5, and no table's *template* grows (checked exhaustively
    through n == 4).

    An *instantiated* program can grow by a few characters, though, because
    the drain's staircase sits one column further right than the branches it
    replaced and :func:`_compact` then has fewer all-blank columns to drop.
    AND-2 is the case: only its ``00`` half is constant, a ``0`` leaf needs
    no drain to halt, so the drain buys nothing there and the committed
    example went 124 to 128 bytes.  It is bounded and shallow-table-only --
    the fold is worth many times that wherever a ``1`` leaf folds at all.
    """
    n = _validate_truth_table(truth_table)
    header = ["{X0}"]
    header.extend(["    "] * 4)
    for i in range(1, n):
        header.append("{X" + str(i) + "}")
        header.extend(["    "] * 3)
    rows = header + _MIDDLE + _tree(list(truth_table))
    return "\n".join(row.rstrip() for row in rows)


def _instantiate_arrowqueue(template: str, bits: list[int]) -> str:
    """Fill an ArrowQueue template's ``{Xi}`` placeholders with the bits.

    ``bits`` is listed most-significant first and must match the template
    built by :func:`arrowqueue`.  Each ``{Xi}`` placeholder is replaced by
    the embedding block that pushes input ``i`` as a direction: a ``1``
    bit's block pushes down and a ``0`` bit's block pushes right, exactly
    once each (the header is a fixed ``4n + 1`` rows, so the middle and tree
    rows below it stay aligned).
    """
    n = len(bits)
    rows = template.split("\n")
    # The header rows are built to a fixed width, but the pointer never
    # travels past the last glyph on a row, so trailing blanks are inert;
    # trim them so the emitted program carries no whitespace it cannot use.
    joined = _header_rows(bits) + rows[4 * n + 1 :]
    return _compact(joined)


def _compact(rows: list[str]) -> str:
    """Drop the wholly blank rows and columns from an instantiated program.

    The blocks are laid out on fixed pitches -- a ``1`` bit's embedding is
    one glyph plus three blank rows, and a tree block pads to 3x3 -- so the
    grid arrives with whole rows and columns that hold no glyph at all.
    They are not spacing the drawing: a blank line carries only straight
    pointer travel (a vertical drop stays in its column, and a run off the
    edge halts either way), so deleting one shortens that travel without
    changing which cell the pointer reaches next or what it pushes and pops
    there.  Deleting rows and columns together keeps every glyph's row and
    column ordering, which is all the routing depends on.

    This runs on the instantiated program rather than in :func:`arrowqueue`
    because the template's blank header rows are reserved slots, not
    padding: :func:`_instantiate_arrowqueue` finds the body by slicing past
    a fixed ``4n + 1`` rows, so compacting them away would misalign it.
    """
    width = max((len(row) for row in rows), default=0)
    padded = [row.ljust(width) for row in rows]
    kept = [row for row in padded if row.strip()]
    if not kept:  # pragma: no cover - every table lays down at least one cell
        return ""
    columns = [x for x in range(width) if any(row[x] != " " for row in kept)]
    return "\n".join("".join(row[x] for x in columns).rstrip() for row in kept)


def home_row(truth_table: str) -> str:
    """Build a Home Row template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Home Row has no input command, so this is a parameterized generator:
    each ``{Xi}`` placeholder becomes a two-character setter at a bit cell
    that the harness fills in per instantiation.  The cell is zero when the
    placeholder is reached, so the setter raises it with ``a`` and then
    either clears it again (``s``) or leaves it (``j``, whose skip does not
    fire on the now-nonzero cell), spending the same width either way.

    Unlike the removed ``n <= 2``
    routing generator (which tried to send the beam to one of ``2**n``
    distinct leaf cells -- a wall past ``n == 2`` on the fixed 5x5 grid),
    this closed-form construction packs the bits into a single binary
    accumulator and then walks a linear chain of leaf checks, so it never
    needs more than a handful of live cells regardless of ``n``.

    A cell holds the current value under test; the setup line seeds a
    second cell with the ASCII digit base (``48``, ``'0'``).  Each of the
    ``n`` bit-packing lines is ``{Xi} l s ffff a{2**(n-1-i)} f l``: the
    ``l``/``s``/``l`` triple is Home Row's position-stable "run once iff
    nonzero, consuming the guard" gate (loops cannot nest -- ``l``s pair
    strictly by order of appearance -- so this gate, not a BF-style bracket
    match, is what makes the packing safe to chain), and its body adds the
    bit's binary weight to the accumulator only when the bit is 1. After
    all ``n`` gates the accumulator holds the combination's integer index
    ``0 .. 2**n - 1``.

    The remaining ``2**n`` lines are a linear equality chain, one per
    index ``k``: ``a ffff l s f s ff l f l f <answer> k ; l f f`` fans the
    accumulator out into a working copy and a backup (destroying the
    accumulator), subtracts ``k`` from the working copy via the leading
    ``a ffff``/``s`` structure, and the position-stable gate on that
    difference either prints the baked answer byte and halts (a match) or
    restores the accumulator from the backup and falls through to test
    ``k + 1``.  The answer byte is a literal ``a`` (or nothing) baked
    directly from ``truth_table[k]`` -- unlike the ``n`` input bits, it is
    known at generation time, not supplied by the harness, so it needs no
    ``{Xi}`` placeholder.  The final line (index ``2**n - 1``) needs no
    restore, since every other index has already been ruled out.
    """
    n = _validate_truth_table(truth_table)
    setup = "aaaaaalsffaaaaaaaaffflf"
    bit_lines = [
        "{X" + str(i) + "}lsffff" + "a" * (2 ** (n - 1 - i)) + "fl" for i in range(n)
    ]
    leaves = [
        "afffflsfsfflflf" + ("a" if bit == "1" else "") + "k;lff"
        for bit in truth_table[:-1]
    ]
    leaves.append("f" + ("a" if truth_table[-1] == "1" else "") + "k;")
    return setup + "".join(bit_lines) + "".join(leaves)
