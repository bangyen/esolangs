"""Execute the group decoder across every runtime address residue."""

import argparse
import itertools

from address17 import ALL2, group_word
from decoder_group import (
    _PARITY,
    _admissible,
    _build,
    _Emission,
    _expected,
    _meaning,
    _run_traced,
    _setup,
)

from esolangs.interpreters.other.malbolge import (
    _advance,
    _crazy,
    _initial_memory,
    _op,
    _State,
)


def _prepare(emission: _Emission) -> tuple[_State, list[int]]:
    """Execute the common source prefix once, stopping before the first read."""
    memory = list(_initial_memory("".join(map(chr, emission.source))))
    state = (0, 0, 0, False)
    for _ in range(100_000):
        if state[1] == emission.row_start:
            return state, memory
        state, writes, output = _advance(state, memory)
        assert output is None
        assert not state[3]
        for address, value in writes:
            memory[address] = value
    raise AssertionError("decoder prefix did not reach its first read")


def _finish(
    state: _State,
    memory: list[int],
    *,
    entry: dict[int, int] | None = None,
    dynamic: frozenset[int] = frozenset(),
) -> list[int]:
    """Execute one decoder continuation without rewriting the base pointer."""
    output = []
    written: set[int] = set()
    for _ in range(10_000):
        if entry is not None:
            _, c, d, _ = state
            op = _op(memory[c], c)
            reads = {c}
            if op in ("j", "i", "*", "p"):
                reads.add(d)
            if op == "i":
                reads.add(memory[d])
            for address in reads - written - dynamic:
                value = memory[address]
                assert entry.setdefault(address, value) == value, (address, value)
        state, writes, effect = _advance(state, memory)
        for address, value in writes:
            assert address != 142
            memory[address] = value
            if entry is not None:
                written.add(address)
        if effect is not None:
            output.append(effect)
        if state[3]:
            return output
    raise AssertionError("runtime decoder did not halt")


def _prefill(base: int, triple: tuple[int, ...]) -> dict[int, int]:
    """Return admissible group characters, a varied neighbour, and fold outputs."""
    cells = {
        base + offset: next(
            char
            for char in _admissible(base + offset)
            if _meaning(char, (base + offset) % 2) == value
        )
        for offset, value in enumerate(triple)
    }
    cells[base + 3] = _admissible(base + 3)[
        (49 * triple[0] + 7 * triple[1] + triple[2]) % 8
    ]
    cells.update({142: base - 1})
    for offset, cell in enumerate((145, 139, 144)):
        cells[cell] = _PARITY[(base + offset) % 2]
    return cells


def main(*, inspect_entry: bool = False, compact: bool = False) -> None:
    """Check all meaning triples at all 94 residues for each of eight rows."""
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    bases = [
        _crazy(ALL2 - 2, group_word(list(bits))) + 1
        for bits in itertools.product((0, 1), repeat=14)
    ]
    total = 0
    for row in range(8):
        emission = _build(
            row,
            group,
            row_offset=200 * row,
            external_pointer=True,
            external_parity=True,
            compact=compact,
        )
        occupied = set(emission.code) | set(emission.data)
        representatives: dict[int, int] = {}
        for base in bases:
            if not any(base + offset in occupied for offset in range(4)):
                representatives.setdefault(base % 94, base)
        assert len(representatives) == 94
        state, prepared = _prepare(emission)
        expected = {
            triple: [ord(_expected(row, triple))]
            for triple in itertools.product(range(7), repeat=3)
        }
        entry: dict[int, int] | None = {} if inspect_entry else None
        for base in representatives.values():
            for triple, wanted in expected.items():
                memory = list(prepared)
                prefill = _prefill(base, triple)
                for address, value in prefill.items():
                    memory[address] = value
                got = _finish(
                    state,
                    memory,
                    entry=entry,
                    dynamic=frozenset(prefill),
                )
                assert got == wanted, (row, base, triple, got, wanted)
                total += 1
        base = next(iter(representatives.values()))
        got, _ = _run_traced(
            "".join(map(chr, emission.source)), prefill=_prefill(base, (0, 0, 0))
        )
        assert got == expected[(0, 0, 0)]
        print(f"row {row}: 94 runtime residues, {94 * 343} decoder executions")
        if entry is not None:
            low = {address: value for address, value in entry.items() if address < 420}
            print(f"row {row}: {len(entry)} static entry cells, {len(low)} low cells")
            print(f"row {row} low entry: {sorted(low.items())}")
            minimal = [0] * len(prepared)
            for address, value in entry.items():
                minimal[address] = value
            for address, value in _prefill(base, (0, 0, 0)).items():
                minimal[address] = value
            assert _finish(state, minimal) == expected[(0, 0, 0)]
            print(f"row {row}: entry-only memory control passed")
    assert total == 8 * 94 * 343
    print(f"runtime group decoder: {total} cases and eight full-source controls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", action="store_true", help="trace first-read values")
    parser.add_argument("--compact", action="store_true", help="use low trampolines")
    args = parser.parse_args()
    main(inspect_entry=args.entry, compact=args.compact)
