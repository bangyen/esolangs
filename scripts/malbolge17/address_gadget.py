"""Emit and execute the three-bit unit used by the seventeen-input fold."""

import itertools

from address17 import ALL2, LOW, gadget, mix, swap

from esolangs.interpreters.other.malbolge import (
    _advance,
    _crazy,
    _initial_memory,
    _op,
)
from esolangs.tools._malbolge_core import _ENTRY, _WORDS, _build_constants, _char_for, _g
from esolangs.tools._malbolge_digits import _GADGET
from esolangs.tools.malbolge import _Planner, _T_HELPERS


def build() -> tuple[str, tuple[int, int, int], int]:
    """Return a real-source gadget and first-slot fold."""
    used = {128, 129}

    def walked(value: int) -> int:
        cell = next(a for a in range(130, _ENTRY) if a not in used and _g(a) == value)
        used.add(cell)
        return cell

    helper = {"all1": 128, "all2": 129}
    for name, value in _T_HELPERS.items():
        helper[name] = walked(value)
    cells = walked(LOW[0]), walked(LOW[1]), walked(LOW[2])
    two = walked(38)
    memory: dict[int, int | None] = {a: _g(a) for a in range(_ENTRY)}
    path = _Planner(_ENTRY + 1, 34 + (7 - _ENTRY) % 94, memory, {})
    path.code[_ENTRY] = "j"
    _build_constants(path, helper)
    for cell in (helper["all1"], helper["all2"]):
        path.op("p", cell)
        path.op("p", cell)
    path.op("*", helper["w"])
    path.op("p", helper["all2"])
    constants = {"K0": helper["z0"], "K1": helper["all1"], "K2": helper["all2"]}
    for operation in _GADGET:
        if operation == "/":
            path.raw("/")
        elif operation[0] == "K":
            path.op("*", constants[operation])
        else:
            path.op("p", cells[int(operation)])
    path.op("*", helper["all1"])
    path.op("p", two)
    path.op("p", cells[1])
    path.op("*", helper["all2"])
    path.op("p", cells[2])
    path.op("*", helper["w"])
    path.op("p", cells[2])
    path.op("*", cells[2])
    path.op("p", cells[1])
    path.op("*", cells[1])
    path.raw("v")
    source = [_char_for("o", a) for a in range(_WORDS)]
    for address, operation in path.code.items():
        source[address] = _char_for(operation, address)
    return "".join(chr(value) for value in source), cells, len(path.code)


def run(
    source: str,
    cells: tuple[int, int, int],
    bits: tuple[int, int, int],
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
            return memory[cells[1]]
    raise AssertionError("gadget did not halt")


def main() -> None:
    """Check all eight real-source executions against the word model."""
    source, cells, size = build()
    for bits in itertools.product(range(2), repeat=3):
        triple = bits[0], bits[1], bits[2]
        u, v = gadget(LOW, [48 + bit for bit in triple])
        expected = mix(mix(ALL2, _crazy(ALL2, v)), swap(u))
        assert run(source, cells, triple) == expected
    print(f"first address slot: 8/8 correct, {size} code cells")


if __name__ == "__main__":
    main()
