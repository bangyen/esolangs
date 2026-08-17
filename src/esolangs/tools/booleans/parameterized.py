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
"""

from collections.abc import Callable
from typing import TypeAlias

from esolangs.tools.booleans.helpers import _validate_truth_table

__all__ = [
    "back",
    "bfpda",
    "bio",
    "bitdeque",
    "instantiate",
    "lamfunc",
    "minsky_swap",
    "nocomment",
    "ram0",
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

    BIO has three registers (``x``, ``y``, ``z``).  ``{Xi}`` is replaced by
    ``0ox`` (increment ``x``) when bit ``i`` is one and by nothing when it
    is zero, so the raw bit lands in ``x``; ``{Ci}`` is the program's
    *runtime* computation of the complement (``0oy 0ix 1oy 1ox }``, which
    sets ``y = 1 - x`` and clears ``x``).  A node tests ``0iy`` for the
    zero-side and reloads ``{Xi}`` for the one-side, clearing each register
    before its loop exits.  Every leaf clears ``x`` and ``y`` so the
    ancestor loops unwind, and builds the result in ``z`` before printing
    it with ``1iz``.
    """
    n = _validate_truth_table(truth_table)

    def leaf(value: str) -> str:
        # build the result in z, print it, then clear x and y so every
        # ancestor loop (which checks x or y) unwinds cleanly
        return "0oz" * (48 + int(value)) + "1iz" + "0ix" + "1ox" + "}0iy" + "1oy" + "}"

    def node(i: int, rows: list[int]) -> str:
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            return leaf(results.pop())
        zero = [r for r in rows if ((r >> (n - 1 - i)) & 1) == 0]
        one = [r for r in rows if ((r >> (n - 1 - i)) & 1) == 1]
        sub0 = node(i + 1, zero)
        sub1 = node(i + 1, one)
        # x = bit, y = 1 - bit; test y for the zero-side, then reload x for
        # the one-side
        return (
            "{X"
            + str(i)
            + "}"
            + "{C"
            + str(i)
            + "}"
            + "0iy"
            + "1oy"
            + sub0
            + "}"
            + "{X"
            + str(i)
            + "}"
            + "0ix"
            + "1ox"
            + sub1
            + "}"
        )

    return node(0, list(range(2**n)))


def back(truth_table: str) -> str:
    r"""Build a Back template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Back is a no-input grid language: a beam bounces across a grid, ``\\``
    and ``/`` reflect its direction, and ``*`` halts, printing the tape.  A
    beam moving right hits ``\\`` and turns down (toward higher rows) or hits
    ``/`` and turns up (toward lower rows, wrapping around).  The generator
    turns that reflection into a decision tree: each ``{Xi}`` placeholder is
    replaced by ``\\`` when bit ``i`` is one and by ``/`` when it is zero, so
    the beam is sent *down* on a one and *up* on a zero.  A ``/`` or ``\\``
    parked at each child row turns the beam back to moving right into that
    child's own region, and each leaf sets the tape bit (``-``) when its
    table entry is one and halts (``*``) printing the tape.
    """
    n = _validate_truth_table(truth_table)
    rows: int = 2 ** (n + 1) - 1
    center: int = 2**n - 1
    # a full tree has 2**(n+1)-1 nodes, each taking two columns
    width = 2 * (2 ** (n + 1) - 1)
    grid = [[" "] * width for _ in range(rows)]

    def row(i: int, j: int) -> int:
        # dig-style placement: a full binary tree of node rows, with the root
        # at row 0 so the beam starts on it
        return int(((2 * j + 1) * 2 ** (n - i) - 1 - center) % rows)

    # assign each node a column via a preorder walk: node, then the zero
    # subtree, then the one subtree.  Children sit to the right of their
    # parent, so a beam turned right travels into a child through empty cells.
    cols: dict[tuple[int, int], int] = {}

    def assign_col(i: int, j: int) -> int:
        if (i, j) in cols:
            return cols[(i, j)]  # pragma: no cover - a tree node is never revisited
        c = len(cols) * 2
        cols[(i, j)] = c
        if i < n:
            assign_col(i + 1, 2 * j)
            assign_col(i + 1, 2 * j + 1)
        return c

    assign_col(0, 0)

    def build(i: int, j: int) -> None:
        r = row(i, j)
        c = cols[(i, j)]
        lo = j * 2 ** (n - i)
        hi = lo + 2 ** (n - i)
        results = {truth_table[k] for k in range(lo, hi)}
        if i == n or len(results) == 1:
            # leaf (or a constant subtree collapsed to a leaf)
            value = results.pop() if i < n else truth_table[j]
            if value == "1":
                grid[r][c] = "-"
                grid[r][c + 1] = "*"
            else:
                grid[r][c] = "*"
            return
        # internal node: the placeholder mirror reflects the beam down (one)
        # or up (zero) into a child region
        grid[r][c] = "{X" + str(i) + "}"
        for child in (0, 1):
            cr = row(i + 1, 2 * j + child)
            # the child row turns the vertical beam back to moving right
            grid[cr][c] = "\\" if child else "/"
        build(i + 1, 2 * j)
        build(i + 1, 2 * j + 1)

    build(0, 0)

    lines = ["".join(ln).rstrip() for ln in grid]
    return "\n".join(lines)


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
    its complement onto the bit stack, and the harness instantiates one
    program per input combination.

    The tree uses the stack as independent guard storage, which the earlier
    assessment missed: a node pushes the complement then the bit (so the bit
    is on top), runs the one-side loop ``[ sub1 @ ]`` when the bit is one,
    pops the bit, runs the zero-side loop ``[ sub0 @ ]`` when the complement
    is one, and pops the complement.  Each subtree is stack-balanced (it
    pushes and pops its own guards, and a leaf pushes the answer bit, prints
    it with ``.``, and pops it), so the outer ``]`` always re-tests its own
    guard.  The one loop clears its guard with ``@`` before exiting, so the
    other side's guard is untouched and the if/else separates cleanly.
    """
    n = _validate_truth_table(truth_table)

    def leaf(value: str) -> str:
        # push the answer bit, print it, pop it (balanced)
        return ("<@" if value == "1" else "<") + ". > "

    def node(i: int, rows: list[int]) -> str:
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            return leaf(results.pop())
        zero = [r for r in rows if ((r >> (n - 1 - i)) & 1) == 0]
        one = [r for r in rows if ((r >> (n - 1 - i)) & 1) == 1]
        sub0 = node(i + 1, zero)
        sub1 = node(i + 1, one)
        return (
            "{C"
            + str(i)
            + "}"
            + "{X"
            + str(i)
            + "}"
            + "[ "
            + sub1
            + " @ ]"
            + " > "
            + "[ "
            + sub0
            + " @ ]"
            + " > "
        )

    return node(0, list(range(2**n)))


def lamfunc(truth_table: str) -> str:
    """Build a Lamfunc template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Lamfunc has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become the binary literal for each input
    bit, and the harness instantiates one program per input combination.

    The template is a decision tree of ``i`` builtins — ``i x y z`` returns
    ``y`` when ``x`` is nonzero else ``z`` — over the embedded bit constants,
    with ``p 0``/``p 1`` at the leaves printing the table's result as binary.
    A subtree whose table slice is a constant collapses to a single leaf, so
    constant rows emit no branching.
    """
    n = _validate_truth_table(truth_table)

    def node(level: int, lo: int, hi: int) -> str:
        results = {truth_table[k] for k in range(lo, hi)}
        if level == n or len(results) == 1:
            return f"p {results.pop()}"
        mid = (lo + hi) // 2
        # i x y z returns y when x is nonzero else z: y is the one-case
        return (
            f"i {{X{level}}} "
            f"{node(level + 1, mid, hi)} "
            f"{node(level + 1, lo, mid)}"
        )

    return node(0, 0, 2**n)


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
