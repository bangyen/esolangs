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


def nocomment(truth_table: str, n: int) -> str:
    """Build a NoComment template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    NoComment has no input command, so this is a parameterized generator: the
    template's ``{Xi}`` placeholders become a constant-length bit setter
    (``c`` for 0, ``i`` for 1, each prefixed by an ``r`` to reach the bit
    cell), and the harness instantiates one program per input combination.

    The program is a decision tree over the embedded bits.  A node moves to a
    per-node skip cell, pushes the zero-subtree length, moves to the bit cell,
    and ``s``-skips to the one-subtree when the bit is one (falling through to
    the zero-subtree otherwise).  A leaf ``o``-prints the table bit added to
    the shared result cell (pre-set to 48), then walks a per-leaf chain of
    ``n i s d f`` stations that ``s``-skip over the other leaves' code to the
    trailing ``c``.  The chains are interleaved through reserved gaps between
    the leaf blocks, so each leaf's skips stay below the 256-cell byte limit
    while never landing inside another leaf's code or a node test.  The
    ``l``/``r`` moves are emitted from each subtree's known start pointer (the
    parent's bit cell), and the setup length cancels out of the skips, so
    every skip value depends only on the tree layout.

    NoComment cells hold bytes, so every skip value must stay below 256; the
    generator is verified for ``n <= 3`` and raises :class:`ValueError`
    beyond that.
    """
    _validate(truth_table, n)
    if n > 3:
        raise ValueError("the NoComment boolean generator supports n <= 3")

    # Tree shape: assign node/leaf ids; a constant subtree collapses to a leaf.
    node_id = 0
    leaf_id = 0

    def shape(rows: list[int], level: int) -> _Node:
        nonlocal node_id, leaf_id
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            lid = leaf_id
            leaf_id += 1
            return ("leaf", lid, int(results.pop()), None, None)
        nid = node_id
        node_id += 1
        zero = [r for r in rows if not ((r >> (n - 1 - level)) & 1)]
        one = [r for r in rows if (r >> (n - 1 - level)) & 1]
        return ("node", nid, level, shape(zero, level + 1), shape(one, level + 1))

    tree = shape(list(range(2**n)), 0)
    m = node_id
    k = leaf_id
    # Bit cells 0..n-1 (the {Xi} placeholders sit on cell 0 and the harness
    # moves right once per bit); the result cell sits just above the bits.
    result_cell = n
    zlen_base = result_cell + 1
    dcell = zlen_base + m  # the per-leaf chain cells come after the zlen cells
    numd = 6  # chain cells per leaf

    def d_of(lid: int, h: int) -> int:
        return dcell + lid * numd + h

    # Emit the tree commands.  Each subtree starts at its parent's bit cell
    # (the ``s`` leaves the pointer there regardless of which way the branch
    # went).
    commands: list[str] = []
    ptr = [0]

    def move(dst: int) -> None:
        while ptr[0] < dst:
            commands.append("r")
            ptr[0] += 1
        while ptr[0] > dst:
            commands.append("l")
            ptr[0] -= 1

    tests: dict[int, list[int]] = {}  # node id -> [test s position, one start]
    leaf_sts: dict[int, list[int]] = {lid: [] for lid in range(k)}
    leaf_out: dict[int, tuple[int, int]] = {}
    node_regions: list[tuple[int, int]] = []

    def leaf_emit(lid: int, value: int) -> None:
        out_start = len(commands)
        move(result_cell)
        if value:
            commands.append("i")
        commands.append("o")
        d = d_of(lid, 0)
        ptr[0] = result_cell
        move(d)
        commands.append("n")
        commands.append("i")
        leaf_sts[lid].append(len(commands))
        commands.append("s")
        commands.append("d")
        commands.append("f")
        leaf_out[lid] = (out_start, len(commands))

    def tree_emit(node: _Node, start: int) -> None:
        ptr[0] = start
        kind, a, b, zero, one = node
        if kind == "leaf":
            leaf_emit(a, b)
            return
        c = zlen_base + a
        nstart = len(commands)
        move(c)
        commands.append("n")
        move(b)  # the bit cell
        tests[a] = [len(commands)]
        commands.append("s")
        node_regions.append((nstart, len(commands)))
        assert zero is not None
        assert one is not None
        tree_emit(zero, b)
        tests[a].append(len(commands))
        tree_emit(one, b)

    # The tree starts where the setup leaves the pointer, on the last chain
    # cell, so the first move cancels out.
    tree_emit(tree, dcell + k * numd - 1)
    commands.append("c")  # the END target every chain skips to

    # Reserve interleaving gaps: the tree is otherwise dense, leaving no room
    # for the per-leaf chains.  Insert PAD dead-space commands after each
    # leaf's station.  These gaps are skipped over by every leaf's hops, so
    # their content is never executed; stations are later placed inside them.
    pad = 16
    for lid in sorted(range(k), reverse=True):
        pos = leaf_out[lid][1]
        commands[pos:pos] = ["c"] * pad
        for sts in leaf_sts.values():
            for j in range(len(sts)):
                if sts[j] >= pos:
                    sts[j] += pad
        for nid in tests:
            for j in range(2):
                if tests[nid][j] >= pos:
                    tests[nid][j] += pad
        for lid2 in leaf_out:
            a, b = leaf_out[lid2]
            leaf_out[lid2] = (
                a + pad if a >= pos else a,
                b + pad if b >= pos else b,
            )
        for j in range(len(node_regions)):
            a, b = node_regions[j]
            node_regions[j] = (a + pad if a >= pos else a, b + pad if b >= pos else b)

    # A leaf's own code spans from its output through the end of its last
    # station.  Inserted stations must not land inside any leaf's code or any
    # node's test code, otherwise they corrupt the moves of that code.
    def leaf_chain_blocked() -> list[tuple[int, int]]:
        return [(leaf_out[lid][0], leaf_sts[lid][-1] + 3) for lid in range(k)]

    def safe_pos(
        target: int,
        lo: int,
        blocked: list[tuple[int, int]],
    ) -> int | None:
        i = max(target, lo)
        while i < len(commands):
            if not any(a <= i < b for a, b in blocked):
                return i
            i += 1
        return None

    used = dict.fromkeys(range(k), 1)
    for _ in range(40):
        end = len(commands) - 1
        moved = False
        for lid in range(k):
            last = leaf_sts[lid][-1]
            if end - last > 255:
                h = used[lid]
                used[lid] += 1
                d = d_of(lid, h)
                blocked = leaf_chain_blocked() + node_regions
                pos = safe_pos(last + 130, last + 1, blocked)
                if pos is None:
                    moved = False
                    break
                prev = d_of(lid, h - 1)
                mv = ["r"] * (d - prev) if d >= prev else ["l"] * (prev - d)
                cmds = [*mv, "n", "i", "s", "d", "f"]
                commands[pos:pos] = cmds
                body_s = pos + len(mv) + 2
                for sts in leaf_sts.values():
                    for j in range(len(sts)):
                        if sts[j] >= pos:
                            sts[j] += len(cmds)
                leaf_sts[lid].append(body_s)
                for nid in tests:
                    for j in range(2):
                        if tests[nid][j] >= pos:
                            tests[nid][j] += len(cmds)
                for lid2 in leaf_out:
                    a, b = leaf_out[lid2]
                    leaf_out[lid2] = (
                        a + len(cmds) if a >= pos else a,
                        b + len(cmds) if b >= pos else b,
                    )
                for j in range(len(node_regions)):
                    a, b = node_regions[j]
                    node_regions[j] = (
                        a + len(cmds) if a >= pos else a,
                        b + len(cmds) if b >= pos else b,
                    )
                moved = True
        if not moved:
            break

    # Every skip value must fit a byte.  The chain hops skip to the start of
    # the next station (or END), and the node tests skip to their one-subtree.
    end = len(commands) - 1
    chain_skips: dict[tuple[int, int], int] = {}

    def sstart(lid: int, h: int) -> int:
        prev = d_of(lid, h - 1) if h > 0 else result_cell
        mvlen = abs(d_of(lid, h) - prev)
        return leaf_sts[lid][h] - 2 - mvlen

    for lid, sts in leaf_sts.items():
        for h in range(len(sts)):
            nxt = sstart(lid, h + 1) if h + 1 < len(sts) else end
            chain_skips[(lid, h)] = nxt - sts[h] - 1
    if any(not 0 <= v < 256 for v in chain_skips.values()):
        raise ValueError(
            "this truth table needs a chain skip beyond the 256-cell byte limit",
        )
    for st, one in tests.values():
        if not 0 < one - st - 1 < 256:
            raise ValueError(
                "this truth table needs a subtree skip beyond the "
                "256-cell byte limit",
            )

    # The setup length cancels out of every skip, so it can be emitted here
    # against the final tree layout.  The {Xi} placeholders all sit on cell 0;
    # the harness moves right once per bit, leaving the pointer on the last
    # bit cell.
    setup: list[str] = ["{X" + str(i) + "}" for i in range(n)]
    setup_ptr = [n - 1]

    def setup_move(dst: int) -> None:
        while setup_ptr[0] < dst:
            setup.append("r")
            setup_ptr[0] += 1
        while setup_ptr[0] > dst:
            setup.append("l")
            setup_ptr[0] -= 1

    setup_move(result_cell)
    setup.extend(["i"] * 48)
    for nid in sorted(tests):
        setup_move(zlen_base + nid)
        st, one = tests[nid]
        setup.extend(["i"] * (one - st - 1))
    for lid in range(k):
        for h in range(numd):
            setup_move(d_of(lid, h))
            setup.extend(["i"] * chain_skips.get((lid, h), 0))

    return "".join(setup + commands)
