"""Boolean-function generator for s*bleq."""

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    decision_tree_tokens,
)


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
    split in any input order. The read block is one instruction per input::

        v_i -2   NXT    # v_i = -byte (always <= 0, so NXT is the next instr)

    A branch then normalizes and tests that stored value in one destructive
    instruction::

        v_j NEG49 ONE   # a one jumps to ONE, a zero falls through

    The tree tests each input at most once on every root-to-leaf path, so the
    destructive branch is safe. This removes the separate normalization and
    its continuation address without limiting input order.

    Hoisting is a saving in its own right, independent of the reorder. The
    node-read build it replaces read at each node, so every leaf had to
    *drain* the reads its untaken siblings never made -- an input-capable
    language reads each of its n inputs exactly once per run whatever the
    table says -- and that drain cost two instructions and a data triple per
    undrained level, per leaf.  The hoisted read block pays once per input
    for the whole program.

    Leaves print ``-3 D 0`` (``D`` a constant 48/49 cell) and halt with
    ``0 0 3``; an entry trampoline keeps -1 in fixed low cell 3.  Whole
    subtrees whose table entries are constant collapse to a leaf.

    S*bleq's operands are addresses, so a cell holding a transient 0/1 is
    misread as a jump target if any ``c`` references it.  The generator
    therefore keeps *constant* cells (``NEG49``, ``D48``, ``D49``, ``HALT``,
    and the ``NXT``/``ONE`` targets, the only cells ever
    used as a ``c`` operand) strictly separate from *value* cells (each
    input's ``v``, written by the read and never used as a ``c`` operand).
    The jump targets are back-patched once the code layout is known.  The
    normalize subtracts the constant in the ``b`` operand, which the
    ``store="b"``/``"ab"`` variants would overwrite, so this generator
    targets base S*bleq (``store="a"``).

    The node-read form is now redundant: the hoisted route has the same
    one-instruction read-and-test shape at a node but shares its input reads
    across the tree. It handles every table alone.
    """
    _validate_truth_table(truth_table)
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _sbleq_hoisted)
    return _sbleq_packed(truth_table)


def _sbleq_packed(truth_table: str) -> str:
    """Emit a linear-size packed-table decoder for S*bleq."""
    n = _validate_truth_table(truth_table)
    instructions: list[tuple[int | str, int | str, str]] = []
    labels: dict[str, int] = {}
    values: dict[str, int] = {
        "ZERO": 0,
        "ONE": 1,
        "NEGONE": -1,
        "NEG48": -_ASCII_ZERO,
        "N": n,
        "INDEX": 0,
        "TMP": 0,
        "BIT": 0,
        "NEG": 0,
        "COUNT": n,
        "OFFSET": 0,
        "TABLE": 0,
        "SHIFT": 0,
        "Q": 0,
        "R": 0,
        "OUT": _ASCII_ZERO,
        "HALT": -1,
    }

    def mark(name: str) -> None:
        labels[name] = len(instructions)

    def emit(a: int | str, b: int | str, target: str = "next") -> int:
        instructions.append((a, b, target))
        return len(instructions) - 1

    def jump(target: str) -> None:
        emit("ZERO", "ZERO", target)

    def clear(dst: str) -> None:
        emit(dst, dst)

    def increment(dst: int | str) -> None:
        emit(dst, "NEGONE")

    def add(dst: str, src: str) -> None:
        clear("NEG")
        emit("NEG", src)
        emit(dst, "NEG")

    def copy(dst: str, src: str) -> None:
        clear(dst)
        add(dst, src)

    def branch_positive(cell: str, positive: str, zero: str) -> None:
        # A positive result falls through; zero branches through c.
        emit(cell, "ZERO", zero)
        jump(positive)

    # Read ASCII bits once and form their binary row index.
    for _ in range(n):
        clear("TMP")
        emit("TMP", -2)
        emit("TMP", "NEG48")
        clear("BIT")
        emit("BIT", "TMP")
        add("INDEX", "INDEX")
        add("INDEX", "BIT")

    mark("select_test")
    branch_positive("INDEX", "select_step", "selected")
    mark("select_step")
    emit("INDEX", "ONE")
    emit("COUNT", "ONE")
    increment("OFFSET")
    branch_positive("COUNT", "select_test", "advance_chunk")
    mark("advance_chunk")
    load_operand_increment = emit(0, "NEGONE")
    add("COUNT", "N")
    clear("OFFSET")
    jump("select_test")

    mark("selected")
    clear("TABLE")
    load_chunk = emit("TABLE", "CHUNK0")
    copy("SHIFT", "OFFSET")
    increment("SHIFT")

    # Divide by two OFFSET+1 times; the last remainder is the selected bit.
    mark("div_init")
    clear("Q")
    clear("R")
    mark("div_test")
    branch_positive("TABLE", "div_first", "division_complete")
    mark("div_first")
    emit("TABLE", "ONE")
    branch_positive("TABLE", "div_pair", "div_odd")
    mark("div_pair")
    emit("TABLE", "ONE")
    increment("Q")
    jump("div_test")
    mark("div_odd")
    increment("R")
    jump("division_complete")

    mark("division_complete")
    emit("SHIFT", "ONE")
    branch_positive("SHIFT", "divide_again", "output")
    mark("divide_again")
    copy("TABLE", "Q")
    jump("div_init")
    mark("output")
    add("OUT", "R")
    emit(-3, "OUT")
    jump("@HALT")

    # Negative packed values let one subtraction load a positive chunk.
    chunks = [
        -sum(
            int(bit) << offset
            for offset, bit in enumerate(truth_table[start : start + n])
        )
        for start in range(0, len(truth_table), n)
    ]

    target_names = [f"TARGET{i}" for i in range(len(instructions))]
    names = [*values, *target_names, *(f"CHUNK{i}" for i in range(len(chunks)))]
    base = 3 * len(instructions)
    address = {name: base + i for i, name in enumerate(names)}
    memory = [0] * (base + len(names))

    def operand(value: int | str) -> int:
        return address[value] if isinstance(value, str) else int(value)

    for i, (a, b, target) in enumerate(instructions):
        if target == "next":
            target_value = 3 * (i + 1)
        elif target.startswith("@"):
            target_value = None
        else:
            target_value = 3 * labels[target]
        target_cell = target_names[i]
        memory[address[target_cell]] = target_value if target_value is not None else 0
        c = address[target[1:]] if target.startswith("@") else address[target_cell]
        memory[3 * i : 3 * i + 3] = [operand(a), operand(b), c]

    for name, value in values.items():
        memory[address[name]] = value
    for i, value in enumerate(chunks):
        memory[address[f"CHUNK{i}"]] = value
    memory[3 * load_operand_increment] = 3 * load_chunk + 1
    return " ".join(map(str, memory))


def _sbleq_hoisted(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's hoisted S*bleq program; see :func:`sbleq`.

    ``perm[k]`` is the input the tree tests at level ``k``; the read block
    stays in input order, so the program consumes its input stream exactly
    as the node-read build did.
    """
    n = _validate_truth_table(truth_table)
    neg49, d48 = 0, 1
    vbase = 4
    nxtbase = vbase + n
    del d48

    # (a operand, b operand, kind, kind's argument); ``a``/``b`` are data
    # offsets made absolute below, and ``kind`` picks how ``c`` is filled.
    reads: list[tuple[int, int, str, int]] = [
        (vbase + i, -2, "nxt", i) for i in range(n)
    ]

    def leaf(_level: int, row: int) -> list[tuple[int, int, str, int]]:
        return [(-3, 1 + int(truth_table[row]), "out", 0), (0, 0, "halt", 0)]

    def node(
        level: int,
        zero: list[tuple[int, int, str, int]],
        one: list[tuple[int, int, str, int]],
        at: int,
    ) -> list[tuple[int, int, str, int]]:
        # A branch spends one instruction before either subtree, so the
        # one-side starts just past this node and its whole zero subtree.
        # The walker hands that index down, which is what the old build
        # reserved a slot and backpatched to get.
        target = 3 * (at + 1 + len(zero))
        return [(vbase + perm[level], neg49, "one", target), *zero, *one]

    instructions = reads + decision_tree_tokens(
        truth_table,
        leaf,
        node,
        parent_width=1,
        start=len(reads),
        collapse=True,
    )

    onebase = nxtbase + n
    one_count = sum(kind == "one" for _a, _b, kind, _arg in instructions)
    data_base = 9
    code_base = data_base + onebase + one_count

    # ``one`` instructions carry their absolute target, and the data block
    # holds those targets in the order the emit loop meets them.
    ones: list[int] = []

    cells: list[int] = []
    for a, b, kind, arg in instructions:
        if kind == "out":
            cells += [-3, data_base + b, 0]
        elif kind == "halt":
            cells += [0, 0, 3]
        elif kind == "nxt":
            cells += [data_base + a, -2, data_base + nxtbase + arg]
        else:
            slot = len(ones)
            ones.append(code_base + arg)
            cells += [data_base + a, data_base + b, data_base + onebase + slot]

    data = (
        [-_ASCII_ONE, _ASCII_ZERO, _ASCII_ONE, -1]
        + [0] * n
        + [code_base + 3 * (i + 1) for i in range(n)]
        + ones
    )
    # Instruction 0 jumps over inert low-address data to the code.  Keeping
    # the data first shortens every repeated a/b/c operand; the large code
    # targets remain values stored once in that data.
    prelude = [0, 0, 6, -1, 0, 0, code_base, 0, 0]
    cells = prelude + data + cells
    return " ".join(map(str, cells))
