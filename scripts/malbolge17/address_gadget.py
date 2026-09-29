"""Emit and execute the ordinary B path of the seventeen-input address fold."""

import itertools

from address17 import LOW, group_word

from esolangs.interpreters.other.malbolge import (
    _advance,
    _initial_memory,
    _op,
)
from esolangs.tools._malbolge_core import (
    _ENTRY,
    _WORDS,
    _build_constants,
    _char_for,
    _g,
)
from esolangs.tools._malbolge_digits import _GADGET
from esolangs.tools.malbolge import _T_HELPERS, _emit_chain, _Planner, _valid_chars


def build(z: int = 0) -> tuple[str, tuple[tuple[int, int, int], ...], int, int]:
    """Return a real-source ordinary address path for fixed ``z``."""
    if z not in (0, 1, 2):
        raise ValueError(z)
    startup = {10: "j", 11: "*", 12: "j", 13: "p", 14: "j", 15: "*", 16: "j", 17: "i"}
    raw = {125: 103, 126: 124}
    used = {*range(18), 125, 126}

    def walked(value: int) -> int:
        cell = next(
            a for a in range(34, _ENTRY) if a not in used and value in _valid_chars(a)
        )
        used.add(cell)
        raw[cell] = value
        return cell

    reset = walked(33), walked(46), walked(81)
    helper = {"all1": walked(_g(128)), "all2": walked(_g(129))}
    for name, value in _T_HELPERS.items():
        helper[name] = walked(value)
    cells = tuple((walked(LOW[0]), walked(LOW[1]), walked(LOW[2])) for _ in range(4))
    twos = tuple(walked(38) for _ in range(5))
    z_load = walked(45) if z == 2 else None
    z_cell = walked(56 if z == 2 else 47 if z == 0 else 45)
    tail_cell = walked(38)
    boot = [_char_for("o", a) for a in range(_ENTRY)]
    for address, operation in startup.items():
        boot[address] = _char_for(operation, address)
    for address, value in raw.items():
        boot[address] = value
    boot_memory = list(_initial_memory("".join(chr(value) for value in boot)))
    state = (0, 0, 0, False)
    for _ in range(18):
        state, writes, _ = _advance(state, boot_memory)
        for address, value in writes:
            boot_memory[address] = value
    assert state[1:] == (3272, 126, False)
    memory: dict[int, int | None] = {a: boot_memory[a] for a in range(_ENTRY)}
    path = _Planner(3272, 126, memory, {})
    path.op("*", reset[0])
    path.op("p", reset[1])
    path.op("p", reset[2])
    _build_constants(path, helper)
    for cell in (helper["all1"], helper["all2"]):
        path.op("p", cell)
        path.op("p", cell)
    path.op("*", helper["w"])
    path.op("p", helper["all2"])
    constants = {"K0": helper["z0"], "K1": helper["all1"], "K2": helper["all2"]}
    if z == 2:
        assert z_load is not None
        _emit_chain(path, z_load, "K2", helper)
        path.op("p", z_cell)
    else:
        _emit_chain(path, z_cell, "K0 K2 K1 K2", helper)
    _emit_chain(path, tail_cell, "K0", helper)
    for group in cells:
        for operation in _GADGET:
            if operation == "/":
                path.raw("/")
            elif operation[0] == "K":
                path.op("*", constants[operation])
            else:
                path.op("p", group[int(operation)])
    swap_cells = cells[0][1], cells[1][1], cells[2][2], cells[3][1], cells[3][2]
    for cell, two in zip(swap_cells, twos, strict=True):
        path.op("*", helper["all1"])
        path.op("p", two)
        path.op("p", cell)
    for group in (*cells[:3], cells[3]):
        path.op("*", helper["all2"])
        path.op("p", group[2])
    path.op("*", helper["w"])
    for group in cells[:3]:
        path.op("p", group[2])
        path.op("*", group[2])
        path.op("p", group[1])
        path.op("*", group[1])
    path.op("p", z_cell)
    path.op("*", z_cell)
    path.op("p", cells[3][2])
    path.op("*", cells[3][2])
    path.op("*", helper["all2"])
    path.op("p", cells[3][1])
    path.op("p", cells[3][2])
    path.op("*", cells[3][2])
    path.op("p", helper["all1"])
    path.op("*", helper["all2"])
    path.op("p", helper["all1"])
    path.op("p", tail_cell)
    path.raw("v")
    source = [_char_for("o", a) for a in range(_WORDS)]
    for address, operation in startup.items():
        source[address] = _char_for(operation, address)
    for address, value in raw.items():
        source[address] = value
    for address, operation in path.code.items():
        source[address] = _char_for(operation, address)
    return (
        "".join(chr(value) for value in source),
        cells,
        tail_cell,
        len(startup) + len(path.code),
    )


def run(
    source: str,
    result_cell: int,
    bits: tuple[int, ...],
) -> int:
    """Execute ``source`` on ``bits`` and return the folded accumulator."""
    memory = list(_initial_memory(source))
    state = (0, 0, 0, False)
    inputs = iter(48 + bit for bit in bits)
    for _ in range(100_000):
        char = next(inputs) if _op(memory[state[1]], state[1]) == "/" else None
        state, writes, _ = _advance(state, memory, char)
        for address, value in writes:
            memory[address] = value
        if state[3]:
            return memory[result_cell]
    raise AssertionError("address fold did not halt")


def main() -> None:
    """Check all 12,288 fixed ordinary paths against the word model."""
    sizes = []
    for z in range(3):
        source, _cells, result_cell, size = build(z)
        prefix = [0, 1] if z == 0 else [1, z - 1]
        for bits in itertools.product(range(2), repeat=12):
            assert run(source, result_cell, bits) == group_word([*prefix, *bits])
        sizes.append(size)
    print(f"fixed ordinary address paths: 12,288/12,288 correct, {sizes} code cells")


if __name__ == "__main__":
    main()
