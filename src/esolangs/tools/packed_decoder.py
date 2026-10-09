"""The packed-table subtract-and-branch decoder S*bleq and Subleq share.

Chunks contain n bits apiece; selection scans chunks and division extracts
the requested bit, so the program is O(T) whatever the table.
"""

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, input_weights


def packed_decoder(truth_table: str, *, direct: bool = False) -> str:
    """Emit a linear-size packed-table decoder for S*bleq.

    An ignored input is read into ``TMP``, which the next read overwrites,
    and never joins the index; the table is packed over the rest, so its
    chunks hold one bit per essential input.  A constant keeps every input.
    """
    weights, projected = input_weights(truth_table, _validate_truth_table(truth_table))
    if any(weights):
        truth_table = projected
    else:
        weights = [1] * len(weights)
    n = sum(map(bool, weights))
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
    emit("OUTPUT" if direct else -3, "OUT")
    jump("halt" if direct else "@HALT")

    # Negative packed values let one subtraction load a positive chunk.
    chunks = [
        -sum(
            int(bit) << offset
            for offset, bit in enumerate(truth_table[start : start + n])
        )
        for start in range(0, len(truth_table), n)
    ]

    if direct:
        names = [*values, *(f"CHUNK{i}" for i in range(len(chunks)))]
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
        for name, value in values.items():
            memory[address[name]] = value
        for i, value in enumerate(chunks):
            memory[address[f"CHUNK{i}"]] = value
        memory[3 * load_operand_increment + 1] = 3 * load_chunk
        return " ".join(map(str, memory))

    target_names = [f"TARGET{i}" for i in range(len(instructions))]
    names = [*values, *target_names, *(f"CHUNK{i}" for i in range(len(chunks)))]
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

    for name, value in values.items():
        memory[address[name]] = value
    for i, value in enumerate(chunks):
        memory[address[f"CHUNK{i}"]] = value
    memory[3 * load_operand_increment] = 3 * load_chunk + 1
    return " ".join(map(str, memory))
