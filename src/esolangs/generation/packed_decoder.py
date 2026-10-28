"""Shared packed subtract-and-branch decoder with constant folding."""

from typing import NamedTuple

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
)


def _sbleq_constant(inputs: int, bit: str, *, direct: bool = False) -> str:
    """Read every input and print the literal in the output's unused third cell."""
    # The reader writes into executed cell 0; the variant discards the write to -2:
    # subtracting cell 0's -2 keeps each ASCII read positive, so it falls through.
    cells = [-1 if direct else -2, 0, 0] * inputs
    literal = 3 * inputs + 2
    output = (literal, -1) if direct else (-3, literal)
    cells.extend((*output, _ASCII_ZERO + int(bit)))
    return " ".join(map(str, cells))


class _Loads(NamedTuple):
    """Instruction indices whose operands are patched once addresses are known."""

    increment: int
    chunk: int


class _Assembler:
    """Subtract-and-branch instructions over named cells, with labels."""

    def __init__(self) -> None:
        self.instructions: list[tuple[int | str, int | str, str]] = []
        self.labels: dict[str, int] = {}

    def mark(self, name: str) -> None:
        self.labels[name] = len(self.instructions)

    def emit(self, a: int | str, b: int | str, target: str = "next") -> int:
        self.instructions.append((a, b, target))
        return len(self.instructions) - 1

    def jump(self, target: str) -> None:
        self.emit("ZERO", "ZERO", target)

    def clear(self, dst: str) -> None:
        self.emit(dst, dst)

    def increment(self, dst: int | str) -> None:
        self.emit(dst, "NEGONE")

    def add(self, dst: str, src: str) -> None:
        self.clear("NEG")
        self.emit("NEG", src)
        self.emit(dst, "NEG")

    def copy(self, dst: str, src: str) -> None:
        self.clear(dst)
        self.add(dst, src)

    def branch_positive(self, cell: str, positive: str, zero: str) -> None:
        # A positive result falls through; zero branches through c.
        self.emit(cell, "ZERO", zero)
        self.jump(positive)


def packed_decoder(
    truth_table: str,
    *,
    direct: bool = False,
) -> str:
    """Emit a linear-size packed-table decoder for the variant.

    An ignored input is read into ``TMP``, which the next read overwrites,
    and never joins the index; the table is packed over the rest, so its
    chunks hold one bit per essential input. Constants read and print a literal.
    A bank storing each equal payload once (two instructions resolve a
    reference) never won on 30 random tables per n=2..12, either variant, and
    won only parity at n=12 (direct), by 7.4%; it was removed.
    """
    total = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
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
    # The projection is dead once the chunks are cut; at the witness
    # arities it is a second full table string beside the caller's.
    del truth_table
    asm = _Assembler()
    _emit_reads(asm, weights, direct=direct)
    loads = _emit_decode(asm, direct=direct)
    values = _cell_values(n, direct=direct)
    layout = _direct_layout if direct else _indirect_layout
    memory, address, chunk_base = layout(asm, [*values], len(chunks))
    for name, value in values.items():
        memory[address[name]] = value
    for index, value in enumerate(chunks):
        memory[chunk_base + index] = value
    del chunks
    _patch_loads(memory, loads, direct=direct)
    return _render(memory)


def _render(memory: list[int]) -> str:
    """Join the memory image in slices, so no full string list is held.

    The flat ``" ".join(map(str, memory))`` materialises one string per
    cell -- at the n = 26 witness that is 2.6M strings, ~190 MB beside
    the image itself.  Slices of 2**15 cells cap the transient at one
    slice's strings plus the joined output.
    """
    step = 1 << 15
    if len(memory) <= step:
        return " ".join(map(str, memory))
    return " ".join(
        " ".join(map(str, memory[start : start + step]))
        for start in range(0, len(memory), step)
    )


def _cell_values(n: int, *, direct: bool) -> dict[str, int]:
    """Return the decoder's named cells and their initial values, in layout order."""
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
    }
    if not direct:
        del values["POS48"]
    return values


def _emit_reads(asm: _Assembler, weights: list[int], *, direct: bool) -> None:
    """Read every input, folding the essential ones into the binary row ``INDEX``."""
    if direct:
        for weight in weights:
            asm.emit("TMP", "INPUT")
            if not weight:
                continue
            asm.emit("TMP", "POS48")
            asm.add("INDEX", "INDEX")
            asm.add("INDEX", "TMP")
        return
    # Read ASCII bits once and form their binary row index.
    for weight in weights:
        asm.clear("TMP")
        asm.emit("TMP", -2)
        if not weight:
            continue
        asm.emit("TMP", "NEG48")
        asm.clear("BIT")
        asm.emit("BIT", "TMP")
        asm.add("INDEX", "INDEX")
        asm.add("INDEX", "BIT")


def _emit_decode(asm: _Assembler, *, direct: bool) -> _Loads:
    """Select ``INDEX``'s chunk, shift out its bit, print it; return the patch sites."""
    asm.mark("select_test")
    asm.branch_positive("INDEX", "select_step", "selected")
    asm.mark("select_step")
    asm.emit("INDEX", "ONE")
    asm.emit("COUNT", "ONE")
    asm.increment("OFFSET")
    asm.branch_positive("COUNT", "select_test", "advance_chunk")
    asm.mark("advance_chunk")
    increment = asm.emit(0, "NEGONE")
    asm.add("COUNT", "N")
    asm.clear("OFFSET")
    asm.jump("select_test")

    asm.mark("selected")
    asm.clear("TABLE")
    chunk = asm.emit("TABLE", "CHUNK0")
    asm.copy("SHIFT", "OFFSET")
    asm.increment("SHIFT")

    # Divide by two OFFSET+1 times; the last remainder is the selected bit.
    asm.mark("div_init")
    asm.clear("Q")
    asm.clear("R")
    asm.mark("div_test")
    asm.branch_positive("TABLE", "div_first", "division_complete")
    asm.mark("div_first")
    asm.emit("TABLE", "ONE")
    asm.branch_positive("TABLE", "div_pair", "div_odd")
    asm.mark("div_pair")
    asm.emit("TABLE", "ONE")
    asm.increment("Q")
    asm.jump("div_test")
    asm.mark("div_odd")
    asm.increment("R")
    asm.jump("division_complete")

    asm.mark("division_complete")
    asm.emit("SHIFT", "ONE")
    asm.branch_positive("SHIFT", "divide_again", "output")
    asm.mark("divide_again")
    asm.copy("TABLE", "Q")
    asm.jump("div_init")
    asm.mark("output")
    asm.add("OUT", "R")
    asm.emit("OUTPUT" if direct else -3, "OUT")
    asm.jump("halt")
    return _Loads(increment, chunk)


def _direct_layout(
    asm: _Assembler, cells: list[str], data_count: int
) -> tuple[list[int], dict[str, int], int]:
    """Lay out the direct variant: literal branch targets, cells after the code.

    Chunk cells follow the named cells consecutively, so only their
    count and base are returned -- naming and addressing 2**n/n chunks
    cost ~0.3 GB at n = 26 for a purely arithmetic layout.
    """
    base = 3 * len(asm.instructions)
    address = {name: base + i for i, name in enumerate(cells)}
    chunk_base = base + len(cells)
    memory = [0] * (chunk_base + data_count)

    def operand(value: int | str) -> int:
        if isinstance(value, str):
            return chunk_base if value == "CHUNK0" else address[value]
        return value

    for i, (a, b, target) in enumerate(asm.instructions):
        c = (
            3 * (i + 1)
            if target == "next"
            else (-1 if target == "halt" else 3 * asm.labels[target])
        )
        if b == "INPUT":
            triple = [-1, operand(a), c]
        elif a == "OUTPUT":
            triple = [operand(b), -1, c]
        else:
            triple = [operand(b), operand(a), c]
        memory[3 * i : 3 * i + 3] = triple
    return memory, address, chunk_base


def _indirect_layout(
    asm: _Assembler, cells: list[str], data_count: int
) -> tuple[list[int], dict[str, int], int]:
    """Lay out the indirect variant: each branch goes through a target cell.

    Chunk cells follow the target cells consecutively; as in the
    direct layout only their count and base are returned.
    """
    target_names = [f"TARGET{i}" for i in range(len(asm.instructions))]
    base = 3 * len(asm.instructions)
    address = {name: base + i for i, name in enumerate([*cells, *target_names])}
    chunk_base = base + len(cells) + len(target_names)
    memory = [0] * (chunk_base + data_count)

    def operand(value: int | str) -> int:
        if isinstance(value, str):
            return chunk_base if value == "CHUNK0" else address[value]
        return int(value)

    for i, (a, b, target) in enumerate(asm.instructions):
        c = address[target_names[i]]
        memory[c] = (
            3 * (i + 1)
            if target == "next"
            else (-1 if target == "halt" else 3 * asm.labels[target])
        )
        memory[3 * i : 3 * i + 3] = [operand(a), operand(b), c]
    return memory, address, chunk_base


def _patch_loads(memory: list[int], loads: _Loads, *, direct: bool) -> None:
    """Point the self-modifying load at the first chunk."""
    source = 0 if direct else 1
    destination = 1 - source
    memory[3 * loads.increment + destination] = 3 * loads.chunk + source
