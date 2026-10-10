"""Shared packed subtract-and-branch decoder with constant and payload folding."""

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, input_weights


def _sbleq_constant(inputs: int, bit: str, *, direct: bool = False) -> str:
    """Read every input and print the literal in the output's unused third cell."""
    # Subleq writes into executed cell 0. S*bleq discards the write to -2:
    # subtracting cell 0's -2 keeps each ASCII read positive, so it falls through.
    cells = [value for _ in range(inputs) for value in (-1 if direct else -2, 0, 0)]
    literal = 3 * inputs + 2
    output = (literal, -1) if direct else (-3, literal)
    cells.extend((*output, _ASCII_ZERO + int(bit)))
    return " ".join(map(str, cells))


def packed_decoder(
    truth_table: str, *, direct: bool = False, keep_constant_layout: bool = False
) -> str:
    """Return the shortest literal or banked decoder, folding constant roots."""
    literal = _packed_build(
        truth_table, direct=direct, keep_constant_layout=keep_constant_layout
    )
    if len(set(truth_table)) == 1:
        return literal
    banked = _packed_build(truth_table, direct=direct, share_chunks=True)
    return min(literal, banked, key=len)


def _packed_build(
    truth_table: str,
    *,
    direct: bool = False,
    keep_constant_layout: bool = False,
    share_chunks: bool = False,
) -> str:
    """Emit a linear-size packed-table decoder for S*bleq.

    An ignored input is read into ``TMP``, which the next read overwrites,
    and never joins the index; the table is packed over the rest, so its
    chunks hold one bit per essential input. Constants read and print a literal.
    A bank stores each equal payload once; two instructions resolve its reference.
    """
    total = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1 and not keep_constant_layout:
        return _sbleq_constant(total, truth_table[0], direct=direct)
    weights, projected = input_weights(truth_table, total)
    if any(weights):
        truth_table = projected
    else:
        weights = [1] * total
    n = sum(map(bool, weights))
    chunks = [
        -int(truth_table[start : start + n][::-1], 2)
        for start in range(0, len(truth_table), n)
    ]
    unique = list(dict.fromkeys(chunks))
    slot_of = {value: i for i, value in enumerate(unique)}
    data_names = (
        [
            *(f"REF{i}" for i in range(len(chunks))),
            *(f"BANK{i}" for i in range(len(unique))),
        ]
        if share_chunks
        else [f"CHUNK{i}" for i in range(len(chunks))]
    )
    instructions: list[tuple[int | str, int | str, str]] = []
    labels: dict[str, int] = {}
    values: dict[str, int] = {
        "ZERO": 0,
        "ONE": 1,
        "NEGONE": -1,
        "NEG48": -_ASCII_ZERO,
        "POS48": _ASCII_ZERO,
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

    if not direct:
        del values["POS48"]

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

    if direct:
        for weight in weights:
            emit("TMP", "INPUT")
            if not weight:
                continue
            emit("TMP", "POS48")
            add("INDEX", "INDEX")
            add("INDEX", "TMP")
    else:
        # Read ASCII bits once and form their binary row index.
        for weight in weights:
            clear("TMP")
            emit("TMP", -2)
            if not weight:
                continue
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
    patch_clear = load_reference = -1
    if share_chunks:
        # Clear the upcoming load's source operand, then load a bank address
        # by subtracting its negative reference. Only this operand is patched.
        patch_clear = emit(0, 0)
        load_reference = emit(0, "REF0")
    load_chunk = emit("TABLE", 0 if share_chunks else "CHUNK0")
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
    emit("OUTPUT" if direct else -3, "OUT")
    jump("halt" if direct else "@HALT")

    def write_data(memory: list[int], address: dict[str, int]) -> None:
        for name, value in values.items():
            memory[address[name]] = value
        if share_chunks:
            for i, value in enumerate(unique):
                memory[address[f"BANK{i}"]] = value
            for i, value in enumerate(chunks):
                memory[address[f"REF{i}"]] = -address[f"BANK{slot_of[value]}"]
        else:
            for i, value in enumerate(chunks):
                memory[address[f"CHUNK{i}"]] = value

    def patch_loads(memory: list[int]) -> None:
        source = 0 if direct else 1
        destination = 1 - source
        load = load_reference if share_chunks else load_chunk
        memory[3 * load_operand_increment + destination] = 3 * load + source
        if share_chunks:
            field = 3 * load_chunk + source
            memory[3 * patch_clear] = field
            memory[3 * patch_clear + 1] = field
            memory[3 * load_reference + destination] = field

    if direct:
        names = [*values, *data_names]
        base = 3 * len(instructions)
        address = {name: base + i for i, name in enumerate(names)}
        memory = [0] * (base + len(names))

        def direct_operand(value: int | str) -> int:
            return address[value] if isinstance(value, str) else value

        for i, (a, b, target) in enumerate(instructions):
            c = (
                3 * (i + 1)
                if target == "next"
                else (-1 if target == "halt" else 3 * labels[target])
            )
            if b == "INPUT":
                triple = [-1, direct_operand(a), c]
            elif a == "OUTPUT":
                triple = [direct_operand(b), -1, c]
            else:
                triple = [direct_operand(b), direct_operand(a), c]
            memory[3 * i : 3 * i + 3] = triple
        write_data(memory, address)
        patch_loads(memory)
        return " ".join(map(str, memory))

    target_names = [f"TARGET{i}" for i in range(len(instructions))]
    names = [*values, *target_names, *data_names]
    base = 3 * len(instructions)
    address = {name: base + i for i, name in enumerate(names)}
    memory = [0] * (base + len(names))

    def operand(value: int | str) -> int:
        return address[value] if isinstance(value, str) else int(value)

    for i, (a, b, target) in enumerate(instructions):
        if target.startswith("@"):
            c = address[target[1:]]
        else:
            c = address[target_names[i]]
            memory[c] = 3 * (i + 1) if target == "next" else 3 * labels[target]
        memory[3 * i : 3 * i + 3] = [operand(a), operand(b), c]

    write_data(memory, address)
    patch_loads(memory)
    return " ".join(map(str, memory))
