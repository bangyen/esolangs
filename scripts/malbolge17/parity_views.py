"""Certify and price the five-base parity view construction."""

import itertools
from pathlib import Path

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools._malbolge_core import _ENTRY, _build_constants, _g
from esolangs.tools.malbolge import (
    _T_HELPERS,
    _chain,
    _emit_chain,
    _Planner,
)

VIEWS = (242, 728, 1700, 2186, 4616, 5102, 6074, 6560, 13364, 13850)
PARITY = (39122, 39365)
BASES = (364, 1093, 2551, 3280, 6925)
# Each stored parity cell rotates into PARITY when loaded with ``*``. A ``p``
# first toggles its differing trit with A = 1458; that operand is also stored
# inverse-rotated so ``*`` loads it. The decoder reads at most three states,
# so three consumable parity cells cover every path.
STORED_PARITY = (58318, 59047)
TOGGLE = 1458
STORED_TOGGLE = 4374
MASK = 729

# Address, target, and construction. Ascending address is the emission order.
CHAINS = (
    (131, BASES[3], "rot rot rot K0 K2 K1 K2"),
    (133, BASES[4], "rot rot rot rot K0 K2 K1 K2"),
    (137, BASES[1], "rot rot rot rot K0 K2 K1 K2"),
    (139, BASES[2], "rot rot rot rot rot K2 K0 K2 K1 K2"),
    (141, STORED_PARITY[0], "rot rot rot rot K2 K0 K2"),
    (145, BASES[0], "rot rot rot rot rot K2 K0 K2 K1 K2"),
    (147, STORED_PARITY[0], "rot rot rot rot K2 K0 K2"),
    (157, STORED_TOGGLE, "K1 rot rot rot"),
    (165, STORED_PARITY[0], "rot rot rot rot K2 K0 K2"),
    (170, MASK, "rot rot rot rot K1 K2"),
    (185, MASK, "rot rot rot rot K1 K2"),
    (197, MASK, "rot rot rot rot K1 K2"),
)


def decoder_depth() -> int:
    """Return the maximum reads on any path of the shipped decoder."""
    path = Path(__file__).with_name("decoder_s5_norepeat.p")
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    start = [int(value) for value in lines[1].split()[1:]]
    delta, pos = [], []
    for line in lines[2:]:
        left, right = line.split("| pos")
        delta.append([int(value) for value in left.split("|")[1].split()])
        pos.append([int(value) for value in right.split()])
    longest = 0
    for values in itertools.product(range(7), repeat=3):
        for row, state in enumerate(start):
            read = []
            while state >= 0:
                cell = pos[state][row]
                read.append(cell)
                state = delta[state][values[cell]]
            assert len(read) == len(set(read))
            longest = max(longest, len(read))
    return longest


def emitted_size() -> tuple[int, int]:
    """Return emitted cells for the five bases, then the complete setup."""

    def measure(chains: tuple[tuple[int, int, str], ...]) -> int:
        used = {128, 129, *(cell for cell, _, _ in CHAINS)}
        memory: dict[int, int | None] = {
            address: _g(address) for address in range(_ENTRY)
        }
        helper = {"all1": 128, "all2": 129}
        for name, value in _T_HELPERS.items():
            address = next(
                a for a in range(130, _ENTRY) if a not in used and _g(a) == value
            )
            used.add(address)
            helper[name] = address

        path = _Planner(_ENTRY + 1, 34 + (7 - _ENTRY) % 94, memory, {})
        path.code[_ENTRY] = "j"
        _build_constants(path, helper)
        for cell in (helper["all1"], helper["all2"]):
            path.op("p", cell)
            path.op("p", cell)
        path.op("*", helper["w"])
        path.op("p", helper["all2"])
        start = path.c
        for cell, _, chain in chains:
            _emit_chain(path, cell, chain, helper)
        return path.c - start

    base_chains = tuple(spec for spec in CHAINS if spec[1] in BASES)
    return measure(base_chains), measure(CHAINS)


def main() -> None:
    """Check the algebra, low-band chains, toggle, and emitted size."""
    assert decoder_depth() == 3
    assert (
        tuple(
            _crazy(PARITY[parity], BASES[state])
            for state in range(5)
            for parity in range(2)
        )
        == VIEWS
    )
    assert _crazy(TOGGLE, STORED_PARITY[0]) == STORED_PARITY[1]
    assert _crazy(TOGGLE, STORED_PARITY[1]) == STORED_PARITY[0]
    assert _crazy(0, STORED_PARITY[0]) == STORED_PARITY[0]
    assert _crazy(0, STORED_PARITY[1]) == STORED_PARITY[1]
    assert tuple(_chain(value, "rot") for value in STORED_PARITY) == PARITY
    assert _chain(STORED_TOGGLE, "rot") == TOGGLE
    for cell, target, chain in CHAINS:
        assert _chain(_g(cell), chain) == target
    bases, total = emitted_size()
    print(f"five bases: {bases} emitted cells")
    print(f"complete view/parity constants: {total} emitted cells")


if __name__ == "__main__":
    main()
