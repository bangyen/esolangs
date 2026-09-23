"""Boolean-function generator for AddSubJump."""

from typing import Any

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    constant_span_test,
    stored_inputs,
)


def addsubjump(truth_table: str) -> str:
    """Build an AddSubJump program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Inputs are read once into a binary row index.  The table is packed into
    ``n``-bit numeric cells; a self-modified operand selects the indexed cell
    and repeated subtraction extracts its bit.  There are ``Theta(T/n)``
    cells of ``O(n)`` digits and the decoder has ``O(n)`` instructions, so
    generation time and rendered size are both ``O(T)``.
    """
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _addsubjump_ordered)
    return _addsubjump_packed(truth_table)


def _addsubjump_packed(truth_table: str) -> str:
    """Emit a linear-size packed-table decoder for AddSubJump."""
    n = _validate_truth_table(truth_table)
    chunk_width = max(n, 1)
    # ``c`` is a literal destination (the wiki's ``goto c``), so a label or
    # ``"next"`` resolves straight into the operand and an ``int`` is already
    # one.  A computed jump is therefore a *write* to an instruction's own
    # ``c`` cell, which is what :func:`branch_positive` does below.
    instructions: list[tuple[int | str, int | str, str | int, int | str]] = []
    labels: dict[str, int] = {}
    values: dict[str, int] = {
        "ZERO": 0,
        "ONE": 1,
        "FOUR": 4,
        "C48": 48,
        "N": chunk_width,
        "INDEX": 0,
        "TMP": 0,
        "COUNT": chunk_width,
        "OFFSET": 0,
        "TABLE": 0,
        "SHIFT": 0,
        "Q": 0,
        "R": 0,
        "OUT": _ASCII_ZERO,
    }
    branch_id = 0

    def mark(name: str) -> None:
        labels[name] = len(instructions)

    def emit(
        a: int | str, b: int | str, target: str | int, d: int | str = "ZERO"
    ) -> int:
        instructions.append((a, b, target, d))
        return len(instructions) - 1

    def jump(target: str) -> None:
        emit("ZERO", "ZERO", target)

    def clear(dst: str) -> None:
        emit(dst, dst, "next", "ONE")

    def branch_positive(cell: str, positive: str, zero: str) -> None:
        """Branch on ``cell > 0`` and restore the reusable jump cell."""
        nonlocal branch_id
        tag = branch_id
        branch_id += 1
        at = len(instructions)
        # The jump cell is the ``c`` operand of the dispatch instruction
        # itself -- there is no indirect jump to hide it behind now.
        jump_cell = 4 * (at + 1) + 2
        positive_trampoline = f"branch_{tag}_positive"
        zero_trampoline = f"branch_{tag}_zero"
        emit(jump_cell, "FOUR", "next", cell)
        # The trampolines are two instructions apart; their midpoint is the
        # value from which adding/subtracting FOUR selects either one.
        emit("ZERO", "ZERO", 4 * (at + 3))
        mark(positive_trampoline)
        emit(jump_cell, "FOUR", "next")
        emit("ZERO", "ZERO", positive)
        mark(zero_trampoline)
        emit(jump_cell, "FOUR", "next", "ONE")
        emit("ZERO", "ZERO", zero)

    # Read every input once and form its binary row index.
    for _ in range(n):
        clear("TMP")
        emit("TMP", -1, "next")
        emit("TMP", "C48", "next", "ONE")
        emit("INDEX", "INDEX", "next")
        emit("INDEX", "TMP", "next")

    mark("select_test")
    branch_positive("INDEX", "select_step", "selected")
    mark("select_step")
    emit("INDEX", "ONE", "next", "ONE")
    emit("COUNT", "ONE", "next", "ONE")
    emit("OFFSET", "ONE", "next")
    branch_positive("COUNT", "select_test", "advance_chunk")
    mark("advance_chunk")
    load_operand_increment = emit(0, "ONE", "next")
    emit("COUNT", "N", "next")
    clear("OFFSET")
    jump("select_test")

    mark("selected")
    clear("TABLE")
    load_chunk = emit("TABLE", "CHUNK0", "next")
    clear("SHIFT")
    emit("SHIFT", "OFFSET", "next")
    emit("SHIFT", "ONE", "div_init")

    # Divide the selected chunk by two OFFSET+1 times.  The final remainder
    # is precisely the indexed truth-table bit.
    mark("div_init")
    clear("Q")
    clear("R")
    mark("div_test")
    branch_positive("TABLE", "div_first", "division_complete")
    mark("div_first")
    emit("TABLE", "ONE", "next", "ONE")
    branch_positive("TABLE", "div_pair", "div_odd")
    mark("div_pair")
    emit("TABLE", "ONE", "next", "ONE")
    emit("Q", "ONE", "div_test")
    mark("div_odd")
    emit("R", "ONE", "division_complete")

    mark("division_complete")
    emit("SHIFT", "ONE", "next", "ONE")
    branch_positive("SHIFT", "divide_again", "output")
    mark("divide_again")
    clear("TABLE")
    emit("TABLE", "Q", "div_init")
    mark("output")
    emit("OUT", "R", "next")
    emit(-1, "OUT", -8)  # print, then halt on the special address

    # Pack n adjacent rows per cell.  Both each value and each cell address
    # have O(log T) digits, while there are O(T/log T) cells.
    chunks = [
        sum(
            int(bit) << offset
            for offset, bit in enumerate(truth_table[start : start + chunk_width])
        )
        for start in range(0, len(truth_table), chunk_width)
    ]

    names = list(values)
    names.extend(f"CHUNK{i}" for i in range(len(chunks)))
    base = 4 * len(instructions)
    address = {name: base + i for i, name in enumerate(names)}

    memory = [0] * (base + len(names))
    for i, (a, b, target, d) in enumerate(instructions):

        def operand(value: int | str) -> int:
            return address[value] if isinstance(value, str) else int(value)

        if target == "next":
            c = 4 * (i + 1)
        elif isinstance(target, int):
            c = target
        else:
            c = 4 * labels[target]
        memory[4 * i : 4 * i + 4] = [operand(a), operand(b), c, operand(d)]

    for name, value in values.items():
        memory[address[name]] = value
    for i, value in enumerate(chunks):
        memory[address[f"CHUNK{i}"]] = value
    # Advancing this instruction's destination advances LOAD_CHUNK's b
    # operand through the contiguous chunk cells.
    memory[4 * load_operand_increment] = 4 * load_chunk + 1
    return " ".join(map(str, memory))


def _addsubjump_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's AddSubJump program; see :func:`addsubjump`.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame; ``perm`` surfaces only where a node names the *stream*
    input whose cell it tests.

    Cells are named by the input they hold (``B{i}`` for stream input ``i``),
    not by the instruction index that allocated them.  The node-read build
    keyed its names off ``len(instructions)``, which a reorder shifts; naming
    by input keeps every reference stable however the tree comes out.
    """
    n = _validate_truth_table(truth_table)

    instructions: list[list[Any]] = []
    values: dict[str, int] = {}
    # ``c`` is a literal destination, so a branch target is resolved into the
    # operand rather than into a cell the jump dereferences.  ``targets`` maps
    # a forward-reference name to the instruction index it will land on.
    targets: dict[str, int] = {}
    # The operand names in the order the instructions mention them, recorded
    # as they are emitted.  The numbering pass below wants exactly this list
    # and used to recover it by re-scanning every operand of every
    # instruction -- 3.5M ``isinstance`` calls on a six-input build, which
    # input-order selection pays once per candidate.
    named: list[str] = []

    def emit(a: object, b: object, c: object, d: int) -> int:
        idx = len(instructions)
        instructions.append([a, b, c, d])
        for v in (a, b):
            if isinstance(v, str):
                named.append(v)
        return idx

    emit(-9, -6, "next", -7)  # enable flag mode
    # The entry jumps over these two instruction-width data blocks.  Their
    # fixed addresses hold the operands repeated throughout the tree:
    # D48=4, D49=5, U=6 and C48=8.
    instructions += [[_ASCII_ZERO, _ASCII_ONE, 0, 0], [-_ASCII_ZERO, 0, 0, 0]]

    stored = stored_inputs(truth_table, perm)

    # The reads, in stream order.  An input no node tests is read into
    # write-only scratch: the contract is that every input is *consumed*,
    # not that every value is kept.
    if any(i not in stored for i in range(n)):
        values["DUMP"] = 0
    for i in range(n):
        if i not in stored:
            emit("DUMP", -1, "next", -7)  # read and discard
            continue
        bit = f"B{i}"
        values[bit] = 0
        emit(bit, -1, "next", -7)  # B += input byte (48/49)
        emit(bit, 8, "next", -7)  # B += -48
        emit(bit, bit, "next", -7)  # double
        emit(bit, bit, "next", -7)  # double -> {0, 4}

    # Rows split most significant first, so the span a node covers is the
    # contiguous ``truth_table[lo:hi]`` and its two halves are that slice cut
    # in two.  Carried as a pair rather than as the list of row indices it
    # used to be: the list rebuilt itself at every node, O(n * 2**n) per
    # candidate, for spans the slice bounds already name.  The fold test is
    # O(1) on the span, so the tree is O(2**n).
    constant = constant_span_test(truth_table)

    def build(level: int, lo: int, hi: int) -> None:
        if constant(lo, hi):
            # Every read already happened up front, so a folded leaf prints
            # and halts with nothing to drain.
            emit(-1, 4 + int(truth_table[lo]), -8, -7)
            return
        half = (hi - lo) // 2
        if perm[level] not in stored:
            # A discarded input has no cell to test.  Its bit cannot change
            # the answer, so both halves are the same function -- descend
            # into the zero half, keeping the row span halving with level.
            build(level + 1, lo, lo + half)
            return
        base = len(instructions)
        bit = f"B{perm[level]}"
        # The jump cell is the goto's own ``c`` operand: with a literal
        # destination the only computed jump is a self-modifying one.  It
        # rests on the zero trampoline two slots on, and ``B`` (0 or 4) moves
        # it to the one trampoline.
        jump = 4 * (base + 1) + 2
        emit(jump, bit, "next", -7)  # c of the goto += B, the hoisted bit
        emit(6, 6, ("init", 4 * (base + 2)), -7)  # goto, target patched above
        ztarget = f"Z{base}"
        otarget = f"O{base}"
        emit(6, 6, ztarget, -7)  # zero trampoline
        emit(6, 6, otarget, -7)  # one trampoline
        targets[ztarget] = len(instructions)
        build(level + 1, lo, lo + half)
        targets[otarget] = len(instructions)
        build(level + 1, lo + half, hi)

    build(0, 0, 2**n)

    base_data = 4 * len(instructions)
    # Insertion-ordered name -> index.  A dict rather than a list because the
    # list spelling scanned twice per call -- ``in`` and then ``.index`` --
    # which is O(names) on a table that calls this once per operand: 1.6M
    # calls and 2.4s of a 3.8s six-input build, the generator's whole cost.
    # ``dict`` preserves insertion order, so the numbering it hands out is
    # the same one the scan produced.
    names: dict[str, int] = {}

    def cell(name: str) -> int:
        index = names.get(name)
        if index is None:
            index = names[name] = len(names)
        return base_data + index

    for name in named:
        names.setdefault(name, len(names))
    for name in values:
        cell(name)

    mem = [0] * (base_data + len(names))
    for i, ins in enumerate(instructions):
        a, b, c, d = ins
        if c == "next":
            # Instruction 0 jumps over the two data blocks that follow it.
            c = 12 if i == 0 else 4 * (i + 1)
        elif isinstance(c, tuple):
            c = c[1]
        elif isinstance(c, str):
            c = 4 * targets[c]
        row = [cell(v) if isinstance(v, str) else v for v in (a, b)]
        mem[4 * i : 4 * i + 4] = [*row, c, d]
    for name, val in values.items():
        mem[cell(name)] = val
    return " ".join(map(str, mem))
