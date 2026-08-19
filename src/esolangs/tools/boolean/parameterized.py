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
increment that loads the raw bit into a register and ``{Ci}`` with a runtime
complement computation; :func:`back` replaces ``{Xi}`` with a ``\\`` or
``/`` mirror so the beam is reflected toward the correct subtree;
:func:`nocomment` replaces ``{Xi}`` with a constant-length tape setter
(``c``/``i``) and routes a decision tree with the ``s`` skip; :func:`bitdeque`,
:func:`ram0`, and :func:`minsky_swap` replace ``{Xi}`` with fixed-length
setters and route a ``POP``/``GOTO``, ``C``/``goto``, or ``~`` decision tree.

**Every input must be embedded exactly once.**  An input-capable language
reads each of its ``n`` inputs exactly once per run; a no-input language's
parameterized generator should match that, so a template may contain each
``{Xi}`` placeholder at most once.  Re-embedding a bit at multiple decision
nodes would let a no-input program "read" an input more than its
input-capable counterpart does, which muddies the generator API.  Each
generator below therefore stores every input once (a tape load, a register
pack, a deque/stack push, a variable, or a mirror) and reads it back, rather
than re-substituting it.

The ``{Ci}`` complement placeholder is the exception: ``nocomment`` and
``bfpda`` embed each input's complement once, because their if/else branch
needs a gate that is nonzero exactly when the bit is zero, and neither
language can compute that complement at runtime -- ``nocomment`` has no flip
(only inc/dec/clear) and ``bfpda``'s ``@`` flips the bit in place, destroying
it, so a decision node cannot hold both ``bi`` and ``~bi`` simultaneously.
So those two emit ``n`` ``{Xi}`` plus ``n`` ``{Ci}``; the other generators
emit only the ``n`` ``{Xi}``.

:func:`dotlang` is the exception in two ways: it reads its answer from
*termination* (a leaf is a halt or a 2x2 hang ring, so ``0``/``1`` is
halt/hang rather than output), and it re-embeds each ``{Xi}``/``{Ci}`` at
every decision node (a dotlang decision tree has no way to store a bit and
read it back, so the junctions are the storage).
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
    "dotlang",
    "eval",
    "instantiate",
    "lamfunc",
    "minsky_swap",
    "nocomment",
    "ram0",
    "wii2d",
    "wii2d_tree",
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


_byte_limit = "this truth table needs a skip beyond the 256-cell byte limit"


def nocomment(truth_table: str) -> str:
    """Build a NoComment template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    NoComment has no input command, so this is a parameterized generator: the
    template's ``{Xi}``/``{Ci}`` placeholders become a constant-length setter
    for each input bit and its complement, and the harness instantiates one
    program per input combination.

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

    # Setup: bits, complements, index, skip cells, output cells, sentinel.
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
    for i in range(n):
        setup.append("{C" + str(i) + "}")
        setup.append("r")
    setup_ptr[0] = 2 * n
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
    template's ``{Xi}``/``{Ci}`` placeholders become a push of the bit and of
    its complement, and the harness instantiates one program per input
    combination.  Each input is embedded once: the load phase pushes every
    ``{Ci} {Xi}`` pair (complement then bit) up front, so the stack holds all
    ``n`` bits and their complements with ``b0`` on top.

    A node tests its bit and *consumes* it for the next level using a
    ``<``-break loop ``[ > one < ] > [ > zero < ] >``: ``[`` enters when the
    bit is one, ``>`` pops it, the one-branch pops the complement (to expose
    the next bit), and ``<`` pushes a fresh zero to break the loop -- which
    works because the guard was already popped, unlike ``[ sub @ ]`` where
    ``@`` needs the guard still on top.  The zero-branch is selected by the
    second loop testing the complement.  A leaf pops the remaining pre-loaded
    bits (``2*(n-level)`` of them) and prints the constant answer.
    """
    n = _validate_truth_table(truth_table)

    # load: push every complement then bit, so top = b0
    head = " ".join("{C" + str(i) + "} {X" + str(i) + "}" for i in range(n - 1, -1, -1))

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
# A full decision tree needs each input re-embedded at every node of its
# level (2**n - 1 junctions), since the pointer visits each junction at most
# once.  WII2D has no memory, so it cannot store each input once and re-read
# it like the tape/register parameterized generators (``bio``/``back``/
# ``ram0``) do; the 2**n - 1 tree is therefore the guaranteed universal
# construction (:func:`wii2d_tree`).  The primary generator (:func:`wii2d`)
# does better by exploiting the accumulator arithmetic: the junctions form a
# *merging chain* (each branch's op cells transform the accumulator and the
# branches re-merge before the next junction), so each input is embedded
# exactly once and the final accumulator decodes to the table entry.  WII2D's
# ops are not monotone (``s`` sends -1 to 1), so the decoding routes can
# distinguish any table -- every 1- and 2-input table and all sampled 3-input
# tables are reachable (verified against the interpreter).  The route op
# sequences are searched per table, and the search may fail for large dense
# tables; the tree is the fallback.

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
    searching.  Larger ``n`` tries the op strings at length 2 through 6 with an
    increasing per-length budget; length 2 suffices for every table through
    three inputs, length 3 for sampled dense tables at four, and length 5-6
    for sampled tables at five.  The requirement sets and preimages are
    bit-vectors (one bit per reachable accumulator value), and routes that
    share a preimage effect are deduplicated, so the search stays tractable at
    the longer lengths.
    """
    import time

    if n == 2:
        return 0, _wii2d_n2_closed_form(table)
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
        for start in range(10):
            result = _wii2d_search_start(n, t, start, seqs, pre, index, deadline)
            if result is not None:
                return start, result
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


def _wii2d_search_start(
    n: int,
    t: list[int],
    start: int,
    seqs: list[str],
    pre: Callable[[int, int], int],
    index: dict[int, int],
    deadline: float,
) -> list[tuple[str, str]] | None:
    """Search the junction routes for one fixed starting accumulator value.

    The requirement sets are bit-vectors over the domain; ``pre`` maps a
    requirement bit-vector to the bit-vector of incoming values a route can
    produce it from.
    """
    import time

    start_bit = 1 << index[start]
    chosen: list[tuple[str, str]] = []
    reqsets = [[1 << index[t[c]] for c in range(2**n)]]

    def search(i: int) -> bool:
        if time.monotonic() > deadline:
            raise TimeoutError
        cur = reqsets[0]  # 2**(i+1) requirements
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
        for e0, r0 in eff0.items():
            for e1, r1 in eff1.items():
                nxt = [e0[p] & e1[p] for p in range(2**i)]
                if not all(nxt):
                    continue
                chosen.append((r0, r1))
                reqsets.insert(0, nxt)
                if i == 0:
                    if start_bit & nxt[0]:
                        return True
                elif search(i - 1):
                    return True
                reqsets.pop(0)
                chosen.pop()
        return False

    try:
        if search(n - 1):
            return list(reversed(chosen))
    except TimeoutError:
        return None
    return None


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
        while parent[cur][0] is not None:
            cur, op = parent[cur]
            ops.append(op)
        out.append("".join(reversed(ops)))
    return out


def _wii2d_layout(
    n: int, start: int, routes: list[tuple[str, str]]
) -> list[str]:
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
    budget it raises :class:`ValueError`.

    The guaranteed universal alternative is :func:`wii2d_tree`, which
    re-embeds each input at every node of a decision tree (2**n - 1
    junctions) and works for any table of any arity.
    """
    n = _validate_truth_table(truth_table)
    result = _wii2d_search(n, truth_table)
    if result is None:
        raise ValueError(
            "the WII2D n-embedding search found no route within its budget; "
            "use wii2d_tree for the guaranteed 2**n - 1 embedding tree"
        )
    start, routes = result
    return "\n".join(_wii2d_layout(n, start, routes))


def _wii2d_tree_layout(n: int, table: str) -> list[str]:
    """Lay out a full decision tree: a junction per tree node.

    One junction per input level, with the leaves holding the table entries.
    The leaf cells are a uniform 7 wide, so the layout is independent of the
    table values and the harness re-mirrors the recursion to fill the
    junction cells.
    """
    t = list(table)
    grid: dict[tuple[int, int], str] = {}

    def out_cells(value: str) -> str:
        # uniform 7 cells so the layout is independent of the table values:
        # 6*** = 48, then a space (0) or '+' (1) yields 48/49 for the '~'
        return "6***" + ("+" if value == "1" else " ") + "~."

    def size(level: int, lo: int, hi: int) -> tuple[int, int]:
        if level == n:
            return (len(out_cells(t[lo])), 1)
        mid = lo + (hi - lo) // 2
        w0, h0 = size(level + 1, lo, mid)
        w1, h1 = size(level + 1, mid, hi)
        return (w0 + 2 + w1, max(h0, h1 + 1))

    def place(level: int, row: int, col: int, lo: int, hi: int) -> None:
        if level == n:
            cells = out_cells(t[lo])
            for k, ch in enumerate(cells):
                grid[(row, col + k)] = ch
            return
        mid = lo + (hi - lo) // 2
        grid[(row, col)] = "X"  # single-char junction placeholder
        w0, h0 = size(level + 1, lo, mid)
        conn_col = col + 1 + w0
        # the 1-branch descends below the left subtree, travels east, and
        # ascends just left of the right subtree; the 0-branch continues east
        # into the left subtree in place
        grid[(row + 1 + h0, col)] = ">"  # turn east on the corridor row
        for c in range(col + 1, conn_col):
            grid[(row + 1 + h0, c)] = " "  # corridor travel
        grid[(row + 1 + h0, conn_col)] = "^"  # turn north
        grid[(row + 1, conn_col)] = ">"  # turn east into the right subtree
        place(level + 1, row, col + 1, lo, mid)  # 0-child on this row
        place(level + 1, row + 1, conn_col + 1, mid, hi)  # 1-child below

    place(0, 1, 2, 0, 2**n)
    grid[(0, 0)] = ">"
    grid[(0, 1)] = "v"  # descend to the root
    grid[(1, 1)] = ">"  # turn east into the root
    grid[(1, 0)] = "!"
    maxr = max(r for r, _ in grid)
    maxc = max(c for _, c in grid)
    rows = [[" "] * (maxc + 1) for _ in range(maxr + 1)]
    for (r, c), ch in grid.items():
        rows[r][c] = ch
    return ["".join(r).rstrip() for r in rows]


def wii2d_tree(truth_table: str) -> str:
    """Build a WII2D decision-tree template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    WII2D has no input command, so this is a parameterized generator: the
    template's single-character junction cells are filled with ``>`` (bit 0)
    or ``v`` (bit 1) by the harness.  This is the guaranteed universal
    construction: a full binary decision tree re-embeds each input at every
    node of its level, so the template has ``2**n - 1`` junction cells and
    works for any table of any arity.  It is the fallback the primary
    :func:`wii2d` notes; that one embeds each input exactly once instead.

    The ``X`` junction cells are ordered by the recursion (root, left
    subtree, right subtree); the harness fills the ``k``-th level's cells
    with the ``k``-th input's bit.
    """
    n = _validate_truth_table(truth_table)
    rows = _wii2d_tree_layout(n, truth_table)
    return "\n".join(rows)


def instantiate_wii2d_tree(template: str, bits: list[int]) -> str:
    """Fill a WII2D decision-tree template's junction cells with the bits.

    ``bits`` is listed most-significant first; the junction cells are filled
    in the recursion order the template was laid out in (root, left subtree,
    right subtree), so each level's cells receive that input's bit.
    """
    rows = [list(r) for r in template.split("\n")]
    n = len(bits)
    depth = n

    def size(level: int, lo: int, hi: int) -> tuple[int, int]:
        if level == depth:
            return (7, 1)  # every leaf is a uniform 7 cells
        mid = lo + (hi - lo) // 2
        w0, h0 = size(level + 1, lo, mid)
        w1, h1 = size(level + 1, mid, hi)
        return (w0 + 2 + w1, max(h0, h1 + 1))

    def fill(level: int, row: int, col: int, lo: int, hi: int) -> None:
        if level == depth:
            return
        mid = lo + (hi - lo) // 2
        rows[row][col] = "v" if bits[level] else ">"
        w0, _ = size(level + 1, lo, mid)
        conn_col = col + 1 + w0
        fill(level + 1, row, col + 1, lo, mid)
        fill(level + 1, row + 1, conn_col + 1, mid, hi)

    fill(0, 1, 2, 0, 2**n)
    return "\n".join("".join(r).rstrip() for r in rows)


def dotlang(truth_table: str) -> str:
    """Build a Dotlang template that evaluates the table by termination.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Dotlang's ``(`` spawns a dot at the matching ``)`` while the caller
    continues, so a junction forks the dot into two and the embedded bit
    kills one of them.  Each ``{Xi}`` gate (and its ``{Ci}`` complement) is
    filled with four cells of pass-through (``a``) or an empty cell (`` ``,
    which pops the dot), so exactly the branch whose gate is open survives;
    it turns down (``v``) and right (``>``) into its subtree.  A leaf is
    either an empty cell (the program halts = 0) or a 2x2 ``v</>^`` loop
    ring (the program hangs = 1), so the harness reads the answer from
    termination via :func:`esolangs.vm.run_until_halt_or_cycle` rather than
    from output (the convention Point Break and ArrowQueue use).

    ``{Xi}`` is a four-character token in a 2D grid, so the template
    reserves four cells per gate and ``set_bit``/``set_comp`` must return
    four characters to keep the columns aligned.  The tree re-embeds input
    ``i`` at ``2**i`` junctions, so unlike the other parameterized
    generators a template holds each ``{Xi}`` (and ``{Ci}``) more than once.
    """
    n = _validate_truth_table(truth_table)
    cells: dict[tuple[int, int], str] = {}

    def put(row: int, col: int, char: str) -> None:
        cells[(row, col)] = char

    def build(row: int, col: int, depth: int, combo: int) -> int:
        if depth == n:
            if truth_table[combo] == "0":
                put(row, col, " ")  # halt: the survivor dies on the empty cell
                return 1
            put(row, col, "v")
            put(row, col + 1, "<")
            put(row + 1, col, ">")
            put(row + 1, col + 1, "^")  # hang: a 2x2 loop ring
            return 2
        put(row, col, "(")
        put(row, col + 1, "(")
        put(row, col + 2, " ")  # the forking dot dies here
        put(row, col + 3, ")")
        for k, char in enumerate(f"{{X{depth}}}"):
            put(row, col + 4 + k, char)
        put(row, col + 8, "v")
        put(row + 1, col + 8, ">")
        width0 = build(row + 1, col + 9, depth + 1, combo * 2)
        close = col + 9 + width0
        put(row, close, ")")
        for k, char in enumerate(f"{{C{depth}}}"):
            put(row, close + 1 + k, char)
        put(row, close + 5, "v")
        put(row + 1, close + 5, ">")
        width1 = build(row + 1, close + 6, depth + 1, combo * 2 + 1)
        return close + 6 + width1 - col

    put(0, 0, "\u2022")
    build(0, 1, 0, 0)
    max_row = max(r for r, _ in cells) + 1
    max_col = max(c for _, c in cells) + 1
    grid = [[" "] * max_col for _ in range(max_row)]
    for (r, c), char in cells.items():
        grid[r][c] = char
    return "\n".join("".join(row) for row in grid)
