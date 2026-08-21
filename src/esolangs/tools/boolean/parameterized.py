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

No generator emits a ``{Ci}`` complement placeholder: ``bfpda``'s node
structure needs a truthy marker to stay on the stack after each bit is
consumed, but the marker's value never depends on the bit, so it is a
constant embedded directly in the template; ``nocomment`` computes each
bit's complement from ``{Xi}`` at runtime instead of embedding it.
"""

from collections.abc import Callable
from typing import TypeAlias

from esolangs.tools.boolean.helpers import _validate_truth_table

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

SetBit = Callable[[int, int], str]
SetComp = Callable[[int, int], str]


def instantiate(
    template: str,
    bits: list[int],
    set_bit: SetBit,
    set_comp: SetComp,
) -> str:
    """Substitute each ``{Xi}``/``{Ci}`` placeholder.

    ``{Xi}`` becomes ``set_bit(i, bit)`` (code that sets input ``i`` to the
    bit) and ``{Ci}`` becomes ``set_comp(i, bit)`` (code that sets it to the
    complement of the bit).  Since the bits are embedded constants, the
    complement is emitted directly rather than computed at runtime.
    """
    for i, bit in enumerate(bits):
        template = template.replace("{X" + str(i) + "}", set_bit(i, bit))
        template = template.replace("{C" + str(i) + "}", set_comp(i, bit))
    return template


def bio(truth_table: str) -> str:
    """Build a BIO template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BIO has three registers (``x``, ``y``, ``z``) and no absolute jumps —
    its ``{``/``}`` loops are structurally matched — so a variable-length
    setter is safe.  Each input is embedded once by packing it into ``x``:
    ``{Xi}`` becomes ``0ox`` repeated by the input's binary weight (``2**w``)
    for a one bit and nothing for a zero, so ``x = sum 2**w_i * bit_i`` is
    the input's numeric index.

    ``y`` is initialized to the table's first entry (``table[0]``), then
    ``2**n - 1`` *nested* loops each decrement ``x`` once (``0ix { 1ox ... }``)
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
        return "0oy" if a == "0" else "1oy"

    pack = " ".join("{X" + str(i) + "}" for i in range(n))
    inner = ""
    for j in range(2**n - 1, 0, -1):
        body = "1ox" + yop(truth_table[j - 1], truth_table[j]) + inner
        inner = "0ix{" + body + "}"
    init = "0oy" if truth_table[0] == "1" else ""
    return pack + " " + init + inner + "0oy" * 48 + "1iy"


def eval(truth_table: str) -> str:  # noqa: A001 - the language is named "Eval"
    """Build an Eval template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Eval has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a bit push on the input stack
    (``0`` for a zero, ```+`` for a one) and the harness instantiates one
    program per input combination.  The tree is stored as a flat, full
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
    """
    n = _validate_truth_table(truth_table)

    def combo(leaf: int) -> tuple[int, ...]:
        """Input bits (most significant first) reaching the heap ``leaf``."""
        path: list[int] = []
        while leaf > 0:
            path.append(0 if leaf % 2 else 1)  # odd = left child = 0 branch
            leaf = (leaf - 1) // 2
        return tuple(reversed(path))

    tree: list[str] = []
    for i in range(2 ** (n + 1) - 1):
        if i < 2**n - 1:  # internal node: test the next input
            tree.append("~=~?" + ";" * (i + 1) + "!")
        else:  # leaf: print the table entry for this path
            index = sum(b << (n - 1 - k) for k, b in enumerate(combo(i)))
            tree.append("0+." if truth_table[index] == "1" else "0.")

    bits = "".join("{X" + str(i) + "}" for i in range(n - 1, -1, -1))
    return f"~{bits}~" + "".join(f'"{t}"' for t in tree) + "*!"


def back(truth_table: str) -> str:
    r"""Build a Back template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Back is a no-input grid language: a beam travels the grid and ``-`` flips
    the current tape bit, ``+`` steps the beam forward when the current bit
    is 0, ``<``/``>`` move the tape pointer, ``\`` reflects the beam down,
    and ``*`` halts printing the tape.  Each input is embedded once by
    filling its tape cell: ``{Xi}`` becomes ``-`` for a one bit and a space
    for a zero, so cells ``0..n-1`` hold the inputs; cells ``n`` and ``n+1``
    are a 0-answer and a 1-answer cell.

    A decision node is ``+\>``: ``+`` tests the current tape bit (advancing
    the beam straight past the ``\`` when it is 0) and ``\`` reflects the
    beam down when it is 1, while ``>`` advances the tape pointer to the next
    input.  Both branches advance the pointer once, so a leaf at depth ``d``
    has the pointer at cell ``d``.  A leaf routes the pointer to the 0- or
    1-answer cell and halts; the cell under the head at halt is the result.
    """
    n = _validate_truth_table(truth_table)

    # load (row 0): fill cells 0..n-1 with the inputs, then the 0/1 answer
    # cells.  A '\' at column `base` (past the load, with a space gap the beam
    # travels through) sends the beam down to the tree on row 1.  The tree
    # lives at columns >= base on rows >= 1, so row 0's placeholder shrink on
    # instantiation does not misalign it.
    load_line = (
        "".join("{X" + str(i) + "}" + (">" if i < n - 1 else "") for i in range(n))
        + ">>-"
        + "<" * (n + 1)
    )
    # The load's placeholders shrink on instantiation, so the tree lives on
    # rows >= 1 (immune to row 0's shrink).  A '\' at row 0 col len(load_line)
    # sends the beam down; it shrinks to tree_col on instantiation.  A '\' on
    # row 1 at tree_col turns the descending beam right into the tree.
    tree_col = 3 * n + 3

    grid: dict[tuple[int, int], str] = {}
    next_row = [2]

    def leaf(level: int, value: str, row: int, col: int) -> None:
        target = n + (1 if value == "1" else 0)
        delta = target - level
        move = (">" if delta >= 0 else "<") * abs(delta)
        for k, ch in enumerate(move + "*"):
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

    grid[(0, len(load_line))] = "\\"  # transition down (shrinks to tree_col)
    grid[(1, tree_col)] = "\\"  # turn the descending beam right
    emit(0, 0, 2**n, 1, tree_col + 1)  # tree root on row 1, moving right
    maxrow = max(r for r, _ in grid)
    maxcol = max(c for _, c in grid)
    rows = [[" "] * (maxcol + 1) for _ in range(maxrow + 1)]
    rows[0][: len(load_line)] = list(load_line)
    for (r, c), ch in grid.items():
        rows[r][c] = ch
    return "\n".join("".join(r).rstrip() for r in rows)


def _cod_reachable(n: int, k: int) -> tuple[set[int], set[int], set[int]]:
    """Combo-index contributions reachable after fork ``k`` (0 if ``k == 0``).

    Returns ``(flat, plus_one, plus_weight)``: the values reachable *before*
    fork ``k`` (``flat``), after taking its "continue" branch (``+1``, an
    artifact of the gauntlet's own bookkeeping consumed by :func:`_cod_fork_box`
    ), and after taking its "peel off" branch (``+ 2**(n-k)``, the bit's
    weight).  Recursive in ``k``: fork ``k``'s reachable set is fork
    ``k - 1``'s two branch sets combined.
    """
    if not k:
        return {0}, {0}, {0}

    prev = _cod_reachable(n, k - 1)
    flat = prev[0] | prev[2]
    return (
        flat,
        {v + 1 for v in flat},
        {v + 2 ** (n - k) for v in flat},
    )


def _cod_gauntlet(vals: set[int]) -> str:
    """Build a gauntlet of ``(``/``<`` steps that survives only ``vals``.

    ``vals`` sorted with a leading 0 gives consecutive gaps; each gap becomes
    a run of ``(`` (decrement) of that length followed by a ``<`` gate, so
    only a cod whose value already matches one of ``vals`` survives to the
    next gate.  A trailing run of ``)`` (up to the maximum value) restores
    the surviving cod to that value for whatever comes next.
    """
    arr = [0, *sorted(vals)]
    res = ""
    for k in range(len(arr) - 1):
        diff = arr[k + 1] - arr[k]
        res += "(" * diff + "<"
    res += ")" * max(arr)
    return res


def _cod_fork_box(n: int, k: int) -> str:
    """Build a private, self-contained 5-row box that forks on bit ``k - 1``.

    Bit ``k`` (1-indexed, weight ``2**(n - k)``) gets its own ``+`` fork:
    one branch continues forward (a net-zero gauntlet -- the value entering
    and leaving is unchanged), the other peels off to a private side row
    (a gauntlet that nets the branch's full weight), and both rejoin at a
    second ``+`` on the main row.  Unlike nesting fork-and-gauntlet routing
    directly (the ``n <= 3`` construction this replaces), every box below
    uses *its own* private cells for both branches -- no box's gauntlet
    cells are reused by another box's routing -- so boxes compose by plain
    horizontal concatenation (see :func:`_cod_combine`) with no risk of one
    box's cod re-entering another box's cells from an unexpected direction
    (the failure mode that blocked a general-``n`` construction before;
    see ``docs/cod_boolean_generator.md``, "Generalizing past n == 3").
    The leading ``?`` marks the box's own entry cell, replaced by the
    previous box's exit (or ``>`` for the first box) when boxes are joined.
    """
    vals = _cod_reachable(n, k)
    gate0 = _cod_gauntlet(vals[1])
    gate1 = _cod_gauntlet(vals[0])
    back0 = _cod_gauntlet(vals[2])[::-1]
    back1 = gate1[::-1]
    diff = ")" * (2 ** (n - k) - 1)

    top = f"+ {gate0} {back0} +"
    bot = f" {gate1} {diff} {back1}"
    length = max(len(top), len(bot))
    top = top.rjust(length)
    bot = bot.rjust(length)
    box = (
        "~" * length + "\n"
        + top + "\n "
        + "~" * (length - 2)
        + " \n" + bot + "\n"
        + "~" * length
    )
    cov = "~" + box.replace("\n", "~\n~") + "~"
    return cov.replace("\n~", "\n?", 1).replace("+~", "+ ")


def _cod_leaf(n: int, k: int, bit: str) -> str:
    """Build the tail of leaf row ``k``: a gauntlet to 0, the answer, ``---``."""
    diff: int = 2**n - k - 1
    output = ")" if bit == "1" else " "
    return "(<" * diff + ")" * diff + f" {output} ---"


def _cod_cascade_row(n: int) -> str:
    """Build the cascade row's chain of ``+<(`` blocks, one per non-final leaf."""
    total: int = 2**n - 1
    return "  " + "+<(" * total


def _cod_tree(n: int, table: str) -> str:
    """Build the ``2**n`` leaf rows, each peeling off one combo's answer."""

    def row(k: int) -> str:
        output = _cod_leaf(n, k, table[k])
        prefix = "~~ " * (k + 1)
        return prefix + output + "\n" + prefix + "~" * len(output)

    total: int = 2**n - 1
    length = 3 * total + 10
    return (
        "~" * length
        + "\n"
        + "\n".join(row(k) for k in range(total))
        + "\n"
        + _cod_cascade_row(n)
        + " "
        + _cod_leaf(n, total, table[total])
        + "\n"
        + "~" * length
    )


def _cod_cascade(n: int, table: str) -> str:
    """Build the leaf cascade (Phase 2): stairstep gates down to each answer.

    Reached with the combo index ``V = sum(bit_i * 2**(n-1-i))`` as the
    cod's value, the cascade's chain of ``+<(`` blocks (:func:`_cod_cascade_row`)
    peels off one copy per step, decrementing the rest; each leaf's own
    gate chain only lets the copy carrying exactly the right number of
    decrements through, so leaf ``k`` fires iff ``V == k``.  Column 1 is a
    pre-built vertical shaft from the entry row straight down to the
    cascade row, used to feed in the combo index from :func:`_cod_fork_box`
    boxes stacked above (see :func:`_cod_combine`).
    """
    t = _cod_tree(n, table)
    r = t.replace("\n", "\n~ ", 2 ** (n + 1) - 1).replace("~ ", "  ", 1)
    return f"~{r}~"


def _cod_combine(blocks: list[str]) -> str:
    """Concatenate grid blocks left to right, padding shorter ones with blanks."""
    lines = [b.split("\n") for b in blocks]
    longest = max(len(block) for block in lines)
    padded = [
        block + [" " * len(block[0])] * (longest - len(block)) for block in lines
    ]
    rows = ("".join(padded[j][i] for j in range(len(blocks))) for i in range(longest))
    return "\n".join(rows)


def cod(truth_table: str) -> str:
    """Build a COD template for an ``n``-input Boolean function, any ``n >= 1``.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    template's ``{X0}``..``{X(n-1)}`` placeholders become the input bits
    (``)`` for a one bit, a space for a zero); the harness's
    :func:`instantiate` fills them, matching every other no-input
    generator's convention.

    The construction has two phases, each built from private, self-
    contained grid blocks joined by plain horizontal concatenation
    (:func:`_cod_combine`) -- no block's cells are reused by another
    block's routing, which is what makes this generalize past the
    hand-built ``n <= 3`` construction it replaces (see
    ``docs/cod_boolean_generator.md``, "Generalizing past n == 3", for the
    re-entry failure mode that blocked a general-``n`` version before):

    Phase 1 assembles the input combo's numeric index ``V = sum(bit_i *
    2**(n-1-i))``: bits ``0..n-2`` each get their own fork-and-gauntlet box
    (:func:`_cod_fork_box`) that adds the bit's weight to the running value,
    and the last bit (weight ``2**0 == 1``) is a bare placeholder cell
    needing no fork of its own.

    Phase 2 (:func:`_cod_cascade`) is a leaf cascade: reached with the cod's
    value equal to ``V``, a chain of ``2**n - 1`` ``+<(`` blocks peels off
    one copy per step, and each leaf's own gate chain only lets through the
    copy carrying exactly the right number of decrements -- so leaf ``k``
    fires iff ``V == k``, prints the table's answer for that leaf (baked in
    directly, ``)`` for a one entry, nothing for a zero), and halts.  Every
    entry is therefore a compile-time constant and the program always
    prints exactly one line.
    """
    n = _validate_truth_table(truth_table)
    if n < 1:
        raise ValueError(f"cod requires n >= 1, got n == {n}")

    blocks = ["~~~\n~> \n~~~"]
    for k in range(n - 1):
        blocks.append(_cod_fork_box(n, k + 1).replace("?", "{X" + str(k) + "}", 1))

    box_rows = _cod_cascade(n, truth_table).split("\n")
    box_rows[1] = "{X" + str(n - 1) + "}" + box_rows[1][1:]
    blocks.append("\n".join(box_rows))

    return _cod_combine(blocks)


_byte_limit = "this truth table needs a skip beyond the 256-cell byte limit"


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
    cells.append((sentinel, 48))
    for j in range(k):
        cells.append((tbase + j, 48 + int(truth_table[j])))
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
    template's ``{Xi}`` placeholders become a push of the bit, and the
    harness instantiates one program per input combination.  Each input is
    embedded once: the load phase pushes every ``<@ {Xi}`` pair (a constant
    1 marker, then the bit) up front, so the stack holds all ``n`` bits and
    markers with ``b0`` on top.

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
    head = " ".join("<@ {X" + str(i) + "}" for i in range(n - 1, -1, -1))

    def leaf(level: int, value: str) -> str:
        # consume the remaining pre-loaded bits, then print the answer
        return "> " * (2 * (n - level)) + ("<@" if value == "1" else "<") + ". > "

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
        return "[ > " + "> " + sub1 + " < ] > [ > " + sub0 + " < ] >"

    return head + " " + node(0, list(range(2**n)))


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
        return (
            f"i vg v{level} "
            f"{node(level + 1, mid, hi)} "
            f"{node(level + 1, lo, mid)}"
        )

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
    tree: list[str] = []

    def emit(level: int, lo: int, hi: int, start: int) -> int:
        """Emit the subtree for rows ``[lo, hi)``; return the next index.

        ``start`` is the instantiated command index where this subtree begins
        (the load block occupies ``2n`` commands), so the emitted ``GOTO``
        operands are correct after substitution.
        """
        vals = {truth_table[r] for r in range(lo, hi)}
        if level == n or len(vals) == 1:
            answer = vals.pop() if level < n else truth_table[lo]
            sub = leaf(answer)
            tree.extend(sub)
            return start + len(sub)
        half = (hi - lo) // 2
        tree.append("POP")
        marker = len(tree)
        tree.append("GOTO@ONE")
        start += 2
        start = emit(level + 1, lo, lo + half, start)  # zero subtree in place
        tree[marker] = f"GOTO {start}"  # the one subtree starts here
        return emit(level + 1, lo + half, hi, start)

    end = emit(0, 0, 2**n, 2 * n)
    return " ".join(head + ["GOTO " + str(end) if t == "GOTO@END" else t for t in tree])


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

    def leaf(answer: str) -> None:
        nonlocal pos
        tokens.append("Z")
        tokens.append("A" if answer == "1" else "Z")
        pos += 2
        tokens.append("END@")
        pos += 1

    def emit(level: int, lo: int, hi: int) -> None:
        nonlocal pos
        vals = {truth_table[r] for r in range(lo, hi)}
        if level == n or len(vals) == 1:
            leaf(vals.pop() if level < n else truth_table[lo])
            return
        half = (hi - lo) // 2
        tokens.append("Z")  # z = the address, then load ram[z]
        tokens.extend("A" for _ in range(level))
        tokens.append("L")
        pos += 1 + level + 1
        tokens.append("C")
        pos += 1
        marker = len(tokens)
        tokens.append("ONE@")
        pos += 1
        emit(level + 1, lo, lo + half)  # zero subtree in place (MSB = 0)
        tokens[marker] = f"ONE@{pos + 1}"  # 1-based, after the zero subtree
        emit(level + 1, lo + half, hi)

    emit(0, 0, 2**n)
    end = pos + 1  # 1-based goto operand just past the last command
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
_FIRST_ONE = ["   *", "   ~", "    ", "    ", "    "]
_FIRST_ZERO = ["   *", "*~* ", "*  *", "*  *", "* * "]
_NEXT_ONE = ["   ~", "    ", "    ", "    "]
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


def _tree(values: list[str]) -> list[str]:
    """Build the full decision tree for the ``2**n`` table values.

    The tree is full (it never collapses a constant slice): every path pops
    all ``n`` bits, so the queue holds exactly the four loop components at
    every leaf, which both leaf types rely on (the ring's corner pops must
    be R, D, L, U in order).
    """
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
    loop components, and routes a full decision tree by popping the bits at
    ``+`` branches.  Each leaf is a 3x3 block: a ``1`` entry is a
    self-sustaining ring and a ``0`` entry is empty (the pointer runs off
    the grid, which halts).
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
    return "\n".join(_header_rows(bits) + rows[4 * n + 1 :]).rstrip("\n")


# --- A Painter Ant (no-input grid language; parameterized convention) ---
#
# Boolean generators for A Painter Ant.
#
# A Painter Ant is a single ant on an infinite grid of black or white cells
# (all black to start).  Lowercase ``n``/``e``/``s``/``w`` move one cell in
# that direction only if the destination is black; uppercase ``N``/``E``/``S``/
# ``W`` move only if the destination is white; ``p``/``P`` paint the current
# cell black/white.  The program runs in an implicit loop: after the last
# instruction the pointer returns to the first.
#
# The wiki defines no I/O, so the generator follows the parameterized
# convention (like ``bio``/``back``/``nocomment``/``bfpda``): the template
# carries ``{X0}`` and ``{X1}`` placeholders for the two input bits, which
# :func:`instantiate` fills with the per-bit routing code.  The answer is the
# **colour of the cell the ant lands on** at the end of a cycle (white is one,
# black is zero), read by a semantic grid model (the interpreter's own output
# is the visited-cell bounding box, which carries no coordinates).
#
# The construction paints the decision-tree leaves and routes the ant to the
# leaf for its inputs.  :func:`_head` paints one leaf per input combination
# and returns to the origin; each leaf is painted ``P`` (white) for a one
# table entry and left unpainted (a space, ignored by the interpreter) for a
# zero.  Only ``P`` is ever used -- the generator never paints a cell black --
# so the white cells are monotone increasing: cycle 1 establishes them and
# every later cycle only re-confirms a subset, which is what makes the
# programs cycle-stable.  The ``body`` then funnels the ant (from whichever
# corner it ends cycle 2 at) to a canonical routing point, and the final
# input's embedding does the last east/west route onto the output leaf.
#
# The head is built generically: for one and two inputs the leaves sit on
# the axes (the final input on ``x = +-2``, the first on ``y = +-2`` or
# ``0``) and the cycle-2 ant dances on the pre-painted stars (see
# ``docs/a_painter_ant_generator.md`` for the ring rule).  For three inputs
# the leaves sit on one row ``y = -2`` at ``x = +-2 +-4 +-8``,
# four cells apart so adjacent stars share their axis cells and symmetric
# across the y-axis.  This one
# ``_head`` handles ``n == 1``, ``n == 2``, and ``n == 3``.
#
# The template routes the first ``n-1`` inputs by their weight (west/north
# for a one bit, east/south for a zero) before the body and the final input
# east/west after it (``WWwWWEEe`` for a one bit and ``NENEESWw`` for a
# zero, an 8-character complement pair that lands on the opposite-coloured
# leaf).  Every table of any input count is supported and every instantiated
# program is a cycle-stable fixed point (the bounding box is identical for
# any whole number of cycles).

# ``{X0}``: non-final inputs route north/south.
_X0 = {1: "nn", 0: "ss"}
# ``{XF}``: the final (least-significant) input routes east/west.
_XF = {1: "WWwWWEEe", 0: "NENEESWw"}
# The inverse of each move direction, for retracing a path.
_OPP = {
    "n": "s",
    "s": "n",
    "e": "w",
    "w": "e",
    "N": "S",
    "S": "N",
    "E": "W",
    "W": "E",
}


def _bit_move(n: int, k: int, bit: int) -> str:
    """Return the moves that input bit ``k`` contributes.

    ``bits`` are most-significant first, so bit ``k`` carries weight
    ``2 ** (n - k)`` and moves on the axis chosen by index parity (``k % 2
    != n % 2`` -> horizontal, else vertical); a set bit moves west/north, a
    cleared bit east/south.  The head walks these moves out to each leaf
    and the routing walks them to read it, so the two always agree.
    """
    mag: int = 2 ** (n - k)
    if k % 2 != n % 2:
        return ("w" if bit else "e") * mag
    return ("n" if bit else "s") * mag


def _reverse_moves(moves: str) -> str:
    """Return ``moves`` reversed with every direction inverted."""
    return "".join(_OPP[c] for c in reversed(moves))


def _leaf_color(truth_table: str, bits: list[int]) -> bool:
    """Return whether to paint the leaf for the input ``bits``.

    ``bits`` is listed most-significant first, so the table index is the
    packed binary value ``sum(bit << (n-1-i))``.
    """
    index = 0
    for n, b in enumerate(bits):
        index += b << (len(bits) - n - 1)
    return truth_table[index] == "1"


def _leaf_positions(n: int) -> list[tuple[int, int, tuple[int, ...]]]:
    """Return ``(x, y, bits)`` for every leaf in head-visit order.

    The coordinates come from the same weighted rule the head walks and the
    routing reads: each bit ``k`` contributes ``+-2 ** (n-k)`` on the axis
    chosen by index parity, with a cleared bit negative.  The head only
    uses the ``bits``; it reaches each leaf by walking those weights, so
    ``(x, y)`` is the mirror position the routing reads.
    """
    out: list[tuple[int, int, tuple[int, ...]]] = []

    for i in range(2**n):
        pads = bin(i)[2:].rjust(n, "0")
        bits = [int(k) for k in pads]
        x = 0
        y = 0

        for k, b in enumerate(bits):
            mag = 2 ** (n - k)

            if not b:
                mag *= -1

            if k % 2 != n % 2:
                x += mag
            else:
                y += mag

        out.append((x, y, tuple(bits)))

    return out


def _head(truth_table: str, bits: list[int]) -> str:
    """Build the A Painter Ant head for an ``n``-input table.

    The head paints every white leaf and returns to the origin.  It walks
    each leaf out and back piecewise -- one weighted move per input bit
    (:func:`_bit_move`), in the same order and direction the routing uses,
    so the outbound path never crosses a previously painted leaf (the
    intermediate cells are never leaf positions) and the reverse path
    retraces it cleanly.  The ``N`` prefix and ``Ssn`` ending are no-ops
    on the empty first cycle; from cycle 2 on the ``WS``/``NE`` anchors
    launch the ant off the leaf onto the painted ring, making the whole
    program a cycle-stable fixed point.
    """
    n = len(bits)
    out = ["N"]

    for _x, _y, leaf_bits in _leaf_positions(n):
        if not _leaf_color(truth_table, list(leaf_bits)):
            out.append(" ")
            continue
        # Odd n starts on a horizontal bit, so its outbound would lead with
        # NE and the reverse path would end on an orphan WS anchor; a
        # leading WS (no moves) flips it to start WS / end NE like n == 2.
        outbound = "WS" if n >= 3 and n % 2 == 1 else ""
        outbound += "".join(
            (
                ("NE" if k % 2 != n % 2 else "WS") + _bit_move(n, k, b)
                if n >= 2
                else _bit_move(n, k, b)
            )
            for k, b in enumerate(leaf_bits)
        )
        out.append(outbound + "P" + _reverse_moves(outbound))

    out.append("Ssn")
    return "".join(out)


def _body() -> str:
    """Generate the routing body.

    The body paints two two-layer stars -- one around the output leaf and
    one around its y-mirror -- so the final input never has to be
    re-embedded: it only routes to whichever star is already painted.
    Each star is walked as a clockwise spiral of ``P`` paints (the ring
    cells at distance 1 and the axis cells at distance 2), and the two
    stars are connected by the black gap between their rings: the star
    centres are four cells apart and each ring reaches one cell toward the
    other, so the gap is ``4 - 2`` east moves on the row above.  The body
    starts and ends on the shared cell at ``(0, +-2)`` -- the canonical
    point the final input's east/west routing leaves from -- and its
    blocked-uppercase returns are the anchors of the cycle-2 dance.
    """
    # West star, entered from the shared cell: east ring cell, then the
    # clockwise spiral (single ring steps, L-shaped detours out to the axis
    # cells, and blocked-uppercase returns from the axis cells), ending on
    # the south-east diagonal.
    west = ("wP", "nP", "wnP", "EsP", "wP", "swP", "WWeP", "sP", "esP", "SSnP", "eP")
    # East (mirror) star, entered after the gap on the south-west diagonal
    # and walked clockwise to the shared west axis cell.
    east = ("NNseP", "SSnP", "eP", "neP", "EEwP", "nP", "wnP", "NNsP", "wP", "sP", "wP")
    gap = 4 - 2  # star centres 4 apart; each ring reaches 1 cell inward
    return "N" + "".join(west) + "e" * gap + "P" + "".join(east) + "S"


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template for an ``n``-input Boolean function.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    returned template contains ``{X0}``..``{Xn-1}`` placeholders that
    :func:`~esolangs.tools.boolean.parameterized.instantiate` fills with
    the per-bit routing.  The answer is the colour of the cell the ant lands
    on after a cycle (white is one, black is zero).

    Every table is supported for any ``n``, and every instantiated program
    is a cycle-stable fixed point.  The first ``n-1`` inputs route by their
    weight (west/north for a one bit, east/south for a zero) before the
    body; the final (least-significant) input routes east/west onto its
    leaf after it.
    """
    n = _validate_truth_table(truth_table)

    # The head paints every leaf; the body paints the two stars; the first
    # n-1 inputs route by weight before the body, and the final
    # (least-significant) input routes east/west onto its leaf after it.
    head = _head(truth_table, [0] * n)
    prefix = "".join("{X" + str(i) + "}" for i in range(n - 1))
    suffix = "{X" + str(n - 1) + "}"

    return head + prefix + _body() + suffix


def _instantiate_apa(template: str, bits: list[int]) -> str:
    """Fill an A Painter Ant template's ``{Xi}`` placeholders.

    Every input except the final one routes piecewise by its weight
    (``2 ** (n - i)`` cells along the index-parity axis, west/north for a
    one bit, east/south for a zero -- :func:`_bit_move`), and the final
    (least-significant) input routes east/west with the ``WWwWWEEe`` /
    ``NENEESWw`` landing dance onto its leaf.  ``bits`` must match the
    template built by :func:`a_painter_ant`.
    """
    n = len(bits)

    def replace(i: int, bit: int) -> str:
        if i == len(bits) - 1:
            return _XF[bit]
        return _bit_move(n, i, bit)

    return instantiate(
        template,
        bits,
        replace,
        lambda _i, _b: "",
    )


# --- WII2D (no-input grid language; parameterized convention) ---
#
# WII2D's only I/O is the ``~`` output; it has no input command, so the
# boolean generator follows the parameterized convention: the template's
# ``{Xi}`` placeholders are junction cells, and the harness instantiates one
# program per input combination by filling each placeholder with ``>`` (bit
# 0, the pointer continues east) or ``v`` (bit 1, the pointer turns south).
#
# A full decision tree would need each input re-embedded at every node of its
# level (2**n - 1 junctions), since the pointer visits each junction at most
# once, but WII2D has no memory to store each input once and re-read it the
# way the tape/register parameterized generators (``bio``/``back``/``ram0``)
# do.  Instead :func:`wii2d` exploits the accumulator arithmetic: the
# junctions form a *merging chain* (each branch's op cells transform the
# accumulator and the branches re-merge before the next junction), so each
# input is embedded exactly once and the final accumulator decodes to the
# table entry.  WII2D's ops are not monotone (``s`` sends -1 to 1), so the
# decoding routes can distinguish any table -- every table through four
# inputs (exhaustively at one through three, sampled dense at four) and
# sampled dense five-input tables are reachable (verified against the
# interpreter), and symmetric tables of any arity are covered by closed
# forms.  The route op sequences are searched per table; the search raises
# :class:`ValueError` when it cannot fit a table in its budget (large dense
# non-symmetric tables past ``n == 5``).

# The op alphabet the search composes per junction branch: digits set the
# accumulator, ``+ - * / s`` are arithmetic, and a space is a no-op.
_WII2D_OPS = ["+", "-", "*", "/", "s"] + [str(d) for d in range(10)]


def _wii2d_apply(ops: str, value: int) -> int:
    """Apply a WII2D op string to an accumulator value (the op cell order)."""
    for op in ops:
        if op == "+":
            value += 1
        elif op == "-":
            value -= 1
        elif op == "*":
            value *= 2
        elif op == "/":
            value //= 2
        elif op == "s":
            value *= value
        elif op != " ":
            value = int(op)
    return value


def _wii2d_search(n: int, table: str) -> tuple[int, list[tuple[str, str]]] | None:
    """Search for the per-junction branch op sequences realizing ``table``.

    A junction chain of length ``n`` (one per input) computes

        acc = R[n-1][b_n-1] ( ... R[0][b_0] ( start ) ... )

    for each input combo, where each ``R[i][b]`` is an op string applied when
    input ``i`` takes value ``b``.  The search finds the ``2n`` op strings and
    a starting accumulator value such that the composition equals the table
    entry for every combo.  It works backward from the last junction (the
    most constrained: its two branches must map the up to 2**(n-1) incoming
    values to the table's two columns), propagating the set of acceptable
    values for each prefix; returns ``(start, routes)`` or ``None`` if the
    budget runs out.

    ``n == 2`` uses a closed form (:func:`_wii2d_n2_closed_form`) instead of
    searching.  Parity and its complement (symmetric tables where the entry
    is the popcount's low bit) get an exact O(1) closed form
    (:func:`_wii2d_parity_routes`) up front: the general search below *can*
    reach parity at maxlen == 2 for every arity tested (up to n == 20), but
    its cost still grows with n (0.01s at n == 12, ~2s at n == 20), so the
    closed form is a speed win, not a reachability one.  Every other
    symmetric table (AND/OR/majority/threshold-k of any arity) is left to the
    general search first, because it is usually faster there too (its
    preimage-effect pruning makes monotone tables cheap); only if every
    length in the general ladder fails does :func:`_wii2d_symmetric_search`
    get a turn, reducing a symmetric table to a popcount accumulator plus a
    length-``n`` decode lookup instead of the full ``2**n``-row table.  That
    reduction is not just a speed trick: no chain with op strings bounded by
    a fixed length L can represent every table once n is large enough.  There
    are at most ``10 * 15 ** (2*n*(L+1))`` distinct chains (2n routes times
    (L+1) choices of alphabet-15 op per cell, times 10 start values) against
    ``2 ** (2**n)`` tables, so universality needs ``L >~ 2**n / (7.8*n)`` --
    vacuous at small n, but it forces L >= 12 at n == 10 and L >= 43 at
    n == 12, both well past the length-6 ladder below.  So the general search
    is *guaranteed* to eventually fail on some tables at high arity
    (majority/threshold-k among them) regardless of how it is tuned, which is
    where the popcount reduction earns its keep.

    For non-symmetric tables, larger ``n`` tries the op strings at length 2
    through 6 with an increasing per-length budget; length 2 suffices for
    every table through three inputs, length 3 for sampled dense tables at
    four, and length 5-6 for sampled tables at five.  The requirement sets
    and preimages are bit-vectors (one bit per reachable accumulator value),
    and routes that share a preimage effect are deduplicated, so the search
    stays tractable at the longer lengths.
    """
    import time

    if n == 2:
        return 0, _wii2d_n2_closed_form(table)
    popcount_map = _wii2d_symmetric_popcount_map(n, table)
    if popcount_map is not None:
        parity_result = _wii2d_parity_routes(n, popcount_map)
        if parity_result is not None:
            return parity_result
    t = [int(c) for c in table]

    # Longer op strings cover denser tables (every table through n == 4 at
    # length 3, sampled n == 5 at length 5-6); the budgets grow accordingly.
    for maxlen, budget in ((2, 4.0), (3, 8.0), (4, 12.0), (5, 30.0), (6, 60.0)):
        domain = _wii2d_domain(maxlen, cap=10**6)
        index = {v: i for i, v in enumerate(domain)}
        seqs = _wii2d_sequences(maxlen, domain)
        inv = []
        for s in seqs:
            m: dict[int, int] = {}
            for v in domain:
                y = _wii2d_apply(s, v)
                m[y] = m.get(y, 0) | (1 << index[v])
            inv.append(m)

        def pre(
            sidx: int,
            targets: int,
            inv: list[dict[int, int]] = inv,
            domain: list[int] = domain,
        ) -> int:
            out = 0
            m = inv[sidx]
            bits = targets
            while bits:
                low = bits & -bits
                out |= m.get(domain[low.bit_length() - 1], 0)
                bits ^= low
            return out

        deadline = time.monotonic() + budget
        result = _wii2d_search_start(n, t, seqs, pre, index, deadline)
        if result is not None:
            return result
    if popcount_map is not None:
        return _wii2d_symmetric_search(n, popcount_map)
    return None


# For n == 2 a closed form exists: ``R0 = (-, *)`` packs bit 0 as -1 (a zero
# bit) or 0 (a one bit), and each branch of the last junction decodes one of
# the table's two columns from that packed value.  On the pair (-1, 0) the
# column pattern maps to a single op: both zero -> the digit 0, 0 then 1 ->
# ``+``, 1 then 0 -> ``s`` (squaring sends -1 to 1), both one -> the digit 1.
_WII2D_N2_DECODE = {(0, 0): "0", (0, 1): "+", (1, 0): "s", (1, 1): "1"}


def _wii2d_n2_closed_form(table: str) -> list[tuple[str, str]]:
    """Return the two-junction routes for a 2-input table, closed form."""
    t = [int(c) for c in table]
    return [
        ("-", "*"),
        (
            _WII2D_N2_DECODE[(t[0], t[2])],  # column for a zero last bit
            _WII2D_N2_DECODE[(t[1], t[3])],  # column for a one last bit
        ),
    ]


def _wii2d_symmetric_popcount_map(n: int, table: str) -> list[int] | None:
    """Return ``table`` as a function of popcount, or ``None`` if not symmetric.

    A table is symmetric when every combo with the same number of set bits
    has the same entry (the language's version of a boolean function that
    doesn't care which inputs are set, only how many).  The returned list has
    ``n + 1`` entries, ``map[p]`` the shared entry for popcount ``p``.
    """
    result: list[int | None] = [None] * (n + 1)
    for combo in range(2**n):
        p = bin(combo).count("1")
        v = int(table[combo])
        if result[p] is None:
            result[p] = v
        elif result[p] != v:
            return None
    return [v for v in result if v is not None]  # every p in 0..n is reachable


def _wii2d_parity_routes(
    n: int, popcount_map: list[int]
) -> tuple[int, list[tuple[str, str]]] | None:
    """Return the exact chain for parity or its complement, else ``None``.

    Parity chains bit 0 straight in (``('', '+')``), then folds every later
    bit with ``('', '-s')``: ``-s`` sends the running value ``v`` to
    ``(v - 1)**2``, which maps 0 -> 1 and 1 -> 0, so a zero bit leaves the
    running parity alone and a one bit flips it, keeping the value in
    ``{0, 1}`` throughout.  The complement (XNOR-of-n) swaps bit 0's branches
    so the chain starts from the flipped bit instead.
    """
    if popcount_map == [p % 2 for p in range(n + 1)]:
        first = ("", "+")
    elif popcount_map == [1 - p % 2 for p in range(n + 1)]:
        first = ("+", "")
    else:
        return None
    routes = [first] + [("", "-s")] * (n - 1)
    return 0, routes


def _wii2d_symmetric_search(
    n: int, popcount_map: list[int]
) -> tuple[int, list[tuple[str, str]]] | None:
    """Reduce a symmetric table to a popcount accumulator plus a small decode.

    The first ``n - 1`` junctions all use ``('', '+')``, so the accumulator
    equals the popcount of the first ``n - 1`` bits (0 through ``n - 1``)
    regardless of the table.  The last junction only has to turn that
    popcount into the table entry, so its two branches are searched over a
    domain of size ``n`` instead of the full ``2**n`` rows the general search
    fits -- a much cheaper problem that stays tractable well past where the
    general chain search starts to struggle, though it can still fail (e.g.
    non-monotone symmetric tables like "exactly k of n ones" for large ``n``)
    since a single op string cannot express every popcount -> bit map.
    """
    import time

    domain_size = n  # popcount before the last bit ranges over 0..n-1
    deadline = time.monotonic() + 8.0
    for maxlen in range(0, 7):
        if time.monotonic() > deadline:
            return None
        dom = _wii2d_domain(maxlen, cap=10**6)
        if not all(p in dom for p in range(domain_size)):
            continue  # op strings this short can't even reach every popcount
        seqs = _wii2d_sequences(maxlen, dom)
        last0 = next(
            (
                s
                for s in seqs
                if all(
                    _wii2d_apply(s, p) == popcount_map[p] for p in range(domain_size)
                )
            ),
            None,
        )
        last1 = next(
            (
                s
                for s in seqs
                if all(
                    _wii2d_apply(s, p) == popcount_map[p + 1]
                    for p in range(domain_size)
                )
            ),
            None,
        )
        if last0 is not None and last1 is not None:
            routes = [("", "+")] * (n - 1) + [(last0, last1)]
            return 0, routes
    return None


def _wii2d_search_start(
    n: int,
    t: list[int],
    seqs: list[str],
    pre: Callable[[int, int], int],
    index: dict[int, int],
    deadline: float,
) -> tuple[int, list[tuple[str, str]]] | None:
    """Search the junction routes, returning ``(start, routes)``.

    The requirement sets are bit-vectors over the domain; ``pre`` maps a
    requirement bit-vector to the bit-vector of incoming values a route can
    produce it from.  The whole search tree (the route pairs tried at every
    junction) is independent of the starting accumulator value -- ``start``
    only decides whether a complete chain is accepted at the leaf -- so the
    chain is searched once and the leaf's requirement set yields every start
    value the chain works for.  A junction's sub-search depends only on its
    requirement set, so results are memoized by ``(junction, requirement set)``
    to avoid re-solving the same sub-problem reached through different parents.
    """
    import time

    start_bits = 0
    for v in range(10):
        if v in index:
            start_bits |= 1 << index[v]
    memo: dict[
        tuple[int, tuple[int, ...]], tuple[list[tuple[str, str]], int] | None
    ] = {}
    reqsets = [[1 << index[t[c]] for c in range(2**n)]]

    def search(i: int) -> tuple[list[tuple[str, str]], int] | None:
        if time.monotonic() > deadline:
            raise TimeoutError
        cur = reqsets[0]  # 2**(i+1) requirements
        key = (i, tuple(cur))
        if key in memo:
            return memo[key]
        # Two routes are interchangeable at this junction when they share the
        # same preimage effect on every requirement (they allow exactly the
        # same incoming values), so deduplicate by that effect to collapse the
        # |seqs|**2 pair search -- dense n == 5 tables exhaust this way.
        eff0: dict[tuple[int, ...], str] = {}
        for si, s in enumerate(seqs):
            eff0.setdefault(tuple(pre(si, cur[2 * p]) for p in range(2**i)), s)
        eff1: dict[tuple[int, ...], str] = {}
        for si, s in enumerate(seqs):
            eff1.setdefault(tuple(pre(si, cur[2 * p + 1]) for p in range(2**i)), s)
        # Try the least-constraining effects first (largest coverage: the most
        # incoming values they accept), so a solution is reached after a handful
        # of sub-problems instead of hundreds of dead ends.
        e0 = sorted(eff0.items(), key=lambda kv: -sum(x.bit_count() for x in kv[0]))
        e1 = sorted(eff1.items(), key=lambda kv: -sum(x.bit_count() for x in kv[0]))
        m = 2**i
        for a, r0 in e0:
            for b, r1 in e1:
                nxt = [0] * m
                ok = True
                for p in range(m):
                    w = a[p] & b[p]
                    if not w:
                        ok = False
                        break
                    nxt[p] = w
                if not ok:
                    continue
                if i == 0:
                    if nxt[0] & start_bits:
                        memo[key] = ([(r0, r1)], nxt[0])
                        return memo[key]
                else:
                    reqsets.insert(0, nxt)
                    sub = search(i - 1)
                    reqsets.pop(0)
                    if sub is not None:
                        memo[key] = (sub[0] + [(r0, r1)], sub[1])
                        return memo[key]
        memo[key] = None
        return None

    try:
        result = search(n - 1)
    except TimeoutError:
        return None
    if result is None:
        return None
    routes, start_set = result
    for v in range(10):
        if v in index and (start_set >> index[v]) & 1:
            return v, routes
    # every accepted `result` has `start_set & start_bits` nonzero (the i == 0
    # acceptance check above requires it, and start_set is that same value
    # threaded back up unchanged), and start_bits is built from exactly the
    # v in range(10) with v in index, so the loop above always returns
    return None  # pragma: no cover


def _wii2d_domain(maxlen: int, cap: int) -> list[int]:
    """Return the values reachable from 0 by op strings up to ``maxlen`` long."""
    dom = {0}
    frontier = {0}
    for _ in range(maxlen):
        nxt: set[int] = set()
        for v in frontier:
            for op in _WII2D_OPS:
                w = _wii2d_apply(op, v)
                if abs(w) <= cap:
                    nxt.add(w)
        frontier = nxt
        dom |= nxt
    return sorted(dom)


def _wii2d_sequences(maxlen: int, domain: list[int]) -> list[str]:
    """All op strings up to ``maxlen`` long, deduplicated by behaviour on the domain.

    The distinct behaviours are reached by breadth-first search (each step
    appends one op and re-dedupes), rather than enumerating the full 15**maxlen
    strings, so the pool stays cheap at the lengths the search ladder needs.
    """
    size = len(domain)
    identity = tuple(range(size))  # the empty string leaves every value alone
    behaviour_index = {identity: ""}  # behaviour (on domain positions) -> op string
    frontier = [identity]
    for _ in range(maxlen):
        nxt: list[tuple[int, ...]] = []
        for b in frontier:
            for op in _WII2D_OPS:
                nb = tuple(_wii2d_apply(op, b[i]) for i in range(size))
                if nb not in behaviour_index:
                    behaviour_index[nb] = ""
                    nxt.append(nb)
        frontier = nxt
    # recover one op string per behaviour by walking BFS parents
    parent: dict[tuple[int, ...], tuple[tuple[int, ...] | None, str]] = {
        identity: (None, "")
    }
    frontier = [identity]
    for _ in range(maxlen):
        nxt = []
        for b in frontier:
            for op in _WII2D_OPS:
                nb = tuple(_wii2d_apply(op, b[i]) for i in range(size))
                if nb in behaviour_index and nb not in parent:
                    parent[nb] = (b, op)
                    nxt.append(nb)
        frontier = nxt
    out: list[str] = []
    for b in behaviour_index:
        ops: list[str] = []
        cur = b
        while (prev := parent[cur][0]) is not None:
            op = parent[cur][1]
            cur = prev
            ops.append(op)
        out.append("".join(reversed(ops)))
    return out


def _wii2d_layout(n: int, start: int, routes: list[tuple[str, str]]) -> list[str]:
    """Lay out the junction chain template.

    ``{Xi}`` placeholders on row 0, each branch's op cells on row 0 (bit 0)
    or on a dedicated detour row below (bit 1), re-merging before the next
    junction.
    """
    c = [0] * n
    c[0] = 4 if start != 0 else 1  # '>' at (0,0), optional digit at (0,1)
    m = [0] * n
    for i in range(n):
        r0, r1 = routes[i]
        m[i] = c[i] + max(4 + len(r0), len(r1) + 1) + 1
        if i + 1 < n:
            c[i + 1] = m[i] + 2
    total_cols = m[n - 1] + 51  # merge + 48 '+' + '~' + '.'
    grid = [[" "] * total_cols for _ in range(n + 1)]
    grid[0][0] = ">"
    if start:
        grid[0][1] = str(start)
    for i in range(n):
        ph = "{X" + str(i) + "}"
        for k, ch in enumerate(ph):
            grid[0][c[i] + k] = ch
        r0, r1 = routes[i]
        for k, ch in enumerate(r0):
            grid[0][c[i] + 4 + k] = ch
        # 1-branch: descend to row i+1, travel east, ascend to the merge
        grid[i + 1][c[i]] = ">"
        for k, ch in enumerate(r1):
            grid[i + 1][c[i] + 1 + k] = ch
        grid[i + 1][m[i]] = "^"
        grid[0][m[i]] = ">"
    base = m[n - 1] + 1
    for k in range(48):
        grid[0][base + k] = "+"
    grid[0][base + 48] = "~"
    grid[0][base + 49] = "."
    grid[1][0] = "!"
    return ["".join(row).rstrip() for row in grid]


def wii2d(truth_table: str) -> str:
    """Build a WII2D template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    WII2D has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders are junction cells that the harness
    fills with ``>`` (bit 0) or ``v`` (bit 1), one program per input
    combination.  Each input is embedded exactly once: the junctions form a
    *merging chain* whose branch op cells transform the accumulator, so the
    final accumulator is the table entry (printed as ``'0'``/``'1'`` after a
    48-shift).

    Two inputs use a closed form (:func:`_wii2d_n2_closed_form`): bit 0 is
    packed as -1/0 and each column of the table is decoded by a single op.
    Larger ``n`` searches for the branch op strings, trying lengths 2 through
    6 with increasing budgets; length 2 covers every table through three
    inputs, length 3 sampled dense tables at four, and lengths 5-6 sampled
    dense tables at five (the earlier ``n == 4`` wall was a length cap, not a
    representation limit).  The requirement sets and preimages are bit-vectors
    and routes that share a preimage effect are deduplicated, keeping the
    longer lengths tractable.  When the search cannot fit the table in its
    budget it raises :class:`ValueError` -- a genuine cap, not a
    representation limit: the counting-bound argument in :func:`_wii2d_search`
    shows no chain with bounded op strings can represent every table once
    ``n`` is large (dense non-symmetric tables past ``n == 5``), so
    large-arity tables are simply out of reach.
    """
    n = _validate_truth_table(truth_table)
    result = _wii2d_search(n, truth_table)
    if result is None:
        raise ValueError(
            "the WII2D n-embedding search found no route within its budget; "
            "dense non-symmetric tables past n == 5 are out of reach"
        )
    start, routes = result
    return "\n".join(_wii2d_layout(n, start, routes))
