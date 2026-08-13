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
    template's ``{Xi}`` placeholders become a constant-length bit setter
    (``c`` for 0, ``i`` for 1, each prefixed by an ``r`` to reach the bit
    cell), and the harness instantiates one program per input combination.

    The program is a decision tree over the embedded bits.  A node moves to a
    per-node skip cell, pushes the zero-subtree length, moves to the bit cell,
    and ``s``-skips to the one-subtree when the bit is one (falling through to
    the zero-subtree otherwise).  A leaf ``o``-prints the table bit added to
    the shared result cell (pre-set to 48), then walks a per-leaf chain of
    ``n s`` stations that ``s``-skip over the other leaves' code to the
    trailing ``c``.  When a subtree is too long for one byte-sized jump, the
    node test instead skips to a chain of relay stations (each an ``n i s d f``
    that returns to the bit cell) spread through the reserved gaps, so a
    subtree of any length is reachable.  The chains are interleaved through
    the gaps between the leaf blocks, never landing inside another leaf's code
    or a node test.  The ``l``/``r`` moves are emitted from each subtree's
    known start pointer (the parent's bit cell), and the setup length cancels
    out of the skips, so every skip value depends only on the tree layout.
    The setup builds each non-zero cell via the stack: ``n`` copies the
    previous cell's value and ``f`` writes it into the next, so cells are
    written in ascending-value order and only the deltas are incremented.

    NoComment cells hold bytes, so every skip value must fit a byte; the
    generator covers every table up to three inputs and any four-input table
    whose skip chains fit the byte limit, raising :class:`ValueError`
    otherwise.
    """
    _validate(truth_table, n)

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
    dcell = zlen_base + m  # per-leaf chain cells after the zlen cells
    numd = 4  # chain cells per leaf
    rcell = dcell + k * numd  # node relay cells beyond the D cells
    maxrelay = 8  # relay cells per node
    tree_start = dcell + k * numd - 1

    def d_of(lid: int, h: int) -> int:
        return dcell + lid * numd + h

    def r_of(nid: int, j: int) -> int:
        return rcell + nid * maxrelay + j

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

    node_level: dict[int, int] = {}
    tests: dict[int, list[int]] = {}  # node id -> [test s position, one start]
    leaf_sts: dict[int, list[int]] = {lid: [] for lid in range(k)}
    leaf_out: dict[int, int] = {}
    node_sts: dict[int, list[int]] = {nid: [] for nid in range(m)}
    relay_blocks: list[tuple[int, int]] = []
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
        leaf_sts[lid].append(len(commands))
        commands.append("s")
        leaf_out[lid] = out_start

    def tree_emit(node: _Node, start: int) -> None:
        ptr[0] = start
        kind, a, b, zero, one = node
        if kind == "leaf":
            leaf_emit(a, b)
            return
        node_level[a] = b
        c = zlen_base + a
        nstart = len(commands)
        move(c)
        commands.append("n")
        move(b)  # the bit cell
        tests[a] = [len(commands)]
        commands.append("s")
        node_regions.append((nstart, len(commands)))
        assert zero is not None  # nosec B101
        assert one is not None  # nosec B101
        tree_emit(zero, b)
        tests[a].append(len(commands))
        tree_emit(one, b)

    # The tree starts where the setup leaves the pointer, on the last D cell,
    # so the first move cancels out.
    tree_emit(tree, tree_start)
    commands.append("c")  # the END target every chain skips to

    # Reserve interleaving gaps: the tree is otherwise dense, leaving no room
    # for the per-leaf chains and node relays.  Insert PAD dead-space commands
    # after each leaf's station.  These gaps are skipped over by every chain,
    # so their content is never executed; stations are later placed inside.
    pad = 16
    for lid in sorted(range(k), reverse=True):
        pos = leaf_sts[lid][0] + 1
        commands[pos:pos] = ["c"] * pad
        for sts in list(leaf_sts.values()) + list(node_sts.values()):
            for j in range(len(sts)):
                if sts[j] >= pos:
                    sts[j] += pad
        for nid in tests:
            for j in range(2):
                if tests[nid][j] >= pos:
                    tests[nid][j] += pad
        for lid2 in leaf_out:
            if leaf_out[lid2] >= pos:
                leaf_out[lid2] += pad
        for j in range(len(node_regions)):
            a, b = node_regions[j]
            node_regions[j] = (a + pad if a >= pos else a, b + pad if b >= pos else b)
        for j in range(len(relay_blocks)):
            a, b = relay_blocks[j]
            relay_blocks[j] = (a + pad if a >= pos else a, b + pad if b >= pos else b)

    # Inserted stations must not land inside any leaf's code, any node's test
    # code, or any already-placed station, otherwise they corrupt the moves.
    def blocked_now() -> list[tuple[int, int]]:
        blocks = []
        for lid in range(k):
            blocks.append((leaf_out[lid], leaf_sts[lid][0] + 1))
            for h in range(1, len(leaf_sts[lid])):
                s = leaf_sts[lid][h]
                blocks.append((s - 2, s + 1))
        blocks += relay_blocks
        blocks += node_regions
        return blocks

    def safe_pos(
        target: int,
        lo: int,
        hi: int,
    ) -> int | None:
        for d in range(0, hi - lo + 1):
            for cand in (target - d, target + d):
                if lo <= cand <= hi and not any(
                    a <= cand < b for a, b in blocked_now()
                ):
                    return cand
        return None

    snapshot = (
        commands[:],
        {lid: sts[:] for lid, sts in leaf_sts.items()},
        {nid: sts[:] for nid, sts in node_sts.items()},
        {nid: [tests[nid][0], tests[nid][1]] for nid in tests},
        dict(leaf_out),
        node_regions[:],
        relay_blocks[:],
    )
    def place(
        gap: int,
    ) -> tuple[dict[tuple[int, int], int], dict[object, int]]:
        commands[:] = snapshot[0]
        leaf_sts.update({lid: sts[:] for lid, sts in snapshot[1].items()})
        node_sts.update({nid: sts[:] for nid, sts in snapshot[2].items()})
        for nid in tests:
            tests[nid] = [snapshot[3][nid][0], snapshot[3][nid][1]]
        leaf_out.clear()
        leaf_out.update(snapshot[4])
        node_regions[:] = snapshot[5]
        relay_blocks[:] = snapshot[6]
        used = dict.fromkeys(range(k), 1)
        for _ in range(80):
            end = len(commands) - 1
            moved = False
            for lid in range(k):
                last = leaf_sts[lid][-1]
                if end - last - 1 > 255:
                    h = used[lid]
                    if h >= numd:
                        raise ValueError(_byte_limit)
                    used[lid] += 1
                    d = d_of(lid, h)
                    pos = safe_pos(last + gap, last + 1, last + 255)
                    if pos is None:
                        raise ValueError(_byte_limit)
                    prev = d_of(lid, h - 1)
                    mv = ["r"] * (d - prev) if d >= prev else ["l"] * (prev - d)
                    cmds = [*mv, "n", "s"]
                    commands[pos:pos] = cmds
                    body_s = pos + len(mv) + 1
                    for sts in list(leaf_sts.values()) + list(node_sts.values()):
                        for j in range(len(sts)):
                            if sts[j] >= pos:
                                sts[j] += len(cmds)
                    leaf_sts[lid].append(body_s)
                    for nid in tests:
                        for j in range(2):
                            if tests[nid][j] >= pos:
                                tests[nid][j] += len(cmds)
                    for lid2 in leaf_out:
                        if leaf_out[lid2] >= pos:
                            leaf_out[lid2] += len(cmds)
                    for j in range(len(node_regions)):
                        a, b = node_regions[j]
                        node_regions[j] = (
                            a + len(cmds) if a >= pos else a,
                            b + len(cmds) if b >= pos else b,
                        )
                    for j in range(len(relay_blocks)):
                        a, b = relay_blocks[j]
                        relay_blocks[j] = (
                            a + len(cmds) if a >= pos else a,
                            b + len(cmds) if b >= pos else b,
                        )
                    moved = True
            for nid in range(m):
                st = tests[nid][0]
                one = tests[nid][1]
                last = node_sts[nid][-1] if node_sts[nid] else st
                if one - last - 1 > 255:
                    j = len(node_sts[nid])
                    if j >= maxrelay:
                        raise ValueError(_byte_limit)
                    r = r_of(nid, j)
                    pos = safe_pos(last + gap, last + 1, last + 255)
                    if pos is None:
                        raise ValueError(_byte_limit)
                    bit = node_level[nid]
                    mv = ["r"] * (r - bit) if r >= bit else ["l"] * (bit - r)
                    back = ["l"] * (r - bit) if r >= bit else ["r"] * (bit - r)
                    cmds = [*mv, "n", *back, "s"]
                    commands[pos:pos] = cmds
                    body_s = pos + len(mv) + 1 + len(back)
                    for sts in list(leaf_sts.values()) + list(node_sts.values()):
                        for j2 in range(len(sts)):
                            if sts[j2] >= pos:
                                sts[j2] += len(cmds)
                    node_sts[nid].append(body_s)
                    for nid2 in tests:
                        for j2 in range(2):
                            if tests[nid2][j2] >= pos:
                                tests[nid2][j2] += len(cmds)
                    for lid in leaf_out:
                        if leaf_out[lid] >= pos:
                            leaf_out[lid] += len(cmds)
                    for j2 in range(len(node_regions)):
                        a, b = node_regions[j2]
                        node_regions[j2] = (
                            a + len(cmds) if a >= pos else a,
                            b + len(cmds) if b >= pos else b,
                        )
                    for j2 in range(len(relay_blocks)):
                        a, b = relay_blocks[j2]
                        relay_blocks[j2] = (
                            a + len(cmds) if a >= pos else a,
                            b + len(cmds) if b >= pos else b,
                        )
                    relay_blocks.append((pos, pos + len(cmds)))
                    moved = True
            if not moved:
                break

        # Every skip value must fit a byte (<= 254 so the station's ``i`` never
        # wraps).  A leaf chain hops from station to station toward the END; a node
        # chain hops from the test through its relays to the one-subtree.
        end = len(commands) - 1
        chain_skips: dict[tuple[int, int], int] = {}

        def sstart(lid: int, h: int) -> int:
            prev = d_of(lid, h - 1) if h > 0 else result_cell
            mvlen = abs(d_of(lid, h) - prev)
            return leaf_sts[lid][h] - 1 - mvlen

        for lid, sts in leaf_sts.items():
            for h in range(len(sts)):
                nxt = sstart(lid, h + 1) if h + 1 < len(sts) else end
                chain_skips[(lid, h)] = nxt - sts[h] - 1
        if any(not 0 <= v < 256 for v in chain_skips.values()):
            raise ValueError(_byte_limit)

        def rstart(nid: int, j: int) -> int:
            bit = node_level[nid]
            r = r_of(nid, j)
            mvlen = abs(r - bit)
            return node_sts[nid][j] - 1 - 2 * mvlen

        zvals: dict[object, int] = {}
        for nid in tests:
            st, one = tests[nid]
            if node_sts[nid]:
                zvals[nid] = rstart(nid, 0) - st - 1
                for j in range(len(node_sts[nid])):
                    nxt = rstart(nid, j + 1) if j + 1 < len(node_sts[nid]) else one
                    zvals[("r", nid, j)] = nxt - node_sts[nid][j] - 1
            else:
                zvals[nid] = one - st - 1
        if any(not 0 < v < 256 for v in zvals.values()):
            raise ValueError(_byte_limit)
        return chain_skips, zvals

    chain_skips: dict[tuple[int, int], int] = {}
    zvals: dict[object, int] = {}
    for gap in (130, 110, 95, 80):
        try:
            chain_skips, zvals = place(gap)
            break
        except ValueError:
            continue
    else:
        raise ValueError(_byte_limit)
    # The setup length cancels out of every skip, so it can be emitted here
    # against the final tree layout.  The {Xi} placeholders all sit on cell 0;
    # the harness moves right once per bit, leaving the pointer on the last
    # bit cell.  The non-zero cells are written in ascending-value order with
    # the stack carry, so only the deltas are incremented.
    cells: list[tuple[int, int]] = [(result_cell, 48)]
    for nid in sorted(tests):
        cells.append((zlen_base + nid, zvals[nid]))
        for j in range(len(node_sts[nid])):
            cells.append((r_of(nid, j), zvals[("r", nid, j)]))
    for lid in range(k):
        for h in range(numd):
            value = chain_skips.get((lid, h), 0)
            if value:
                cells.append((d_of(lid, h), value))
    cells.sort(key=lambda cv: cv[1])

    setup: list[str] = ["{X" + str(i) + "}" for i in range(n)]
    setup_ptr = [n - 1]

    def setup_move(dst: int) -> None:
        while setup_ptr[0] < dst:
            setup.append("r")
            setup_ptr[0] += 1
        while setup_ptr[0] > dst:
            setup.append("l")
            setup_ptr[0] -= 1

    first_addr, first_value = cells[0]
    setup_move(first_addr)
    setup.extend(["i"] * first_value)
    prev_value = first_value
    for addr, value in cells[1:]:
        setup.append("n")  # push the current cell's finalized value
        setup_move(addr)
        setup.append("f")  # write the carried value into this cell
        diff = value - prev_value
        if diff > 0:
            setup.extend(["i"] * diff)
        else:
            setup.extend(["d"] * -diff)
        prev_value = value
    # the tree's first move starts from its start pointer, so park there
    setup_move(tree_start)

    return "".join(setup + commands)
