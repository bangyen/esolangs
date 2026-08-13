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
(``c``/``i``) and routes a decision tree with the ``s`` skip.
"""

from collections.abc import Callable
from typing import TypeAlias

__all__ = ["back", "bio", "instantiate", "nocomment"]

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


def _validate(truth_table: str, n: int) -> None:
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")


def bio(truth_table: str, n: int) -> str:
    """Build a BIO template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

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
    _validate(truth_table, n)

    def set_bit(_i: int, bit: int) -> str:
        return (
            "0ox" * bit
        )  # pragma: no cover - bio returns a template; the harness injects bits

    def set_comp(_i: int, _bit: int) -> str:
        # y = 1 - x, computed at runtime from the raw bit in x (x cleared)
        return "0oy" + "0ix" + "1oy" + "1ox" + "}"  # pragma: no cover - see set_bit

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


def back(truth_table: str, n: int) -> str:
    r"""Build a Back template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

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
    _validate(truth_table, n)
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


def nocomment(truth_table: str, n: int) -> str:
    """Build a NoComment template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

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
    _validate(truth_table, n)
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
