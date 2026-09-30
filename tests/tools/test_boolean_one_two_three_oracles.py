"""Check every separation law through the interpreter, without builder replay."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine
from esolangs.tools.one_two_three import _LAWS, _construct_small, _separated


def _instantiate(template: str, bits: str) -> str:
    pieces = template.split("$")
    assert len(pieces) == len(bits) + 1
    return (
        "".join(
            piece + ("1" if bit == "1" else "2")
            for piece, bit in zip(pieces, bits, strict=False)
        )
        + pieces[-1]
    )


def _prefix_state(code: str) -> tuple[int, frozenset[int]]:
    machine = _Machine(code, ScriptedIO())
    seen = set()
    for _ in range(10000):
        if machine.ip >= len(code):
            return machine.pos, machine.bits
        assert machine.state not in seen, (code, "prefix loops")
        seen.add(machine.state)
        machine.step()
    raise AssertionError("prefix did not reach its boundary")


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "law"), [(n, law) for n, laws in _LAWS.items() for law in range(len(laws))]
)
def test_law_prefix_and_all_row_states_match_the_interpreter(n: int, law: int) -> None:
    walks, displacements = _LAWS[n][law]
    seed = "".join("2" * distance + "$" for distance in walks)
    rows = [format(row, f"0{n}b") for row in range(2**n)]
    # Choose the first clean landing from executed states, not builder probes.
    for distance in range(4 * 2**n + 9):
        states = [
            _prefix_state(_instantiate(seed + "2" * distance, bits)) for bits in rows
        ]
        if all(pos >= 0 and pos not in marked for pos, marked in states):
            break
    else:
        raise AssertionError("law has no clean seed close")
    prefix = seed + "2" * distance + "33"
    prefix += "".join(
        ("1" if index % 2 == 0 else "2") * width + "33"
        for index, width in enumerate(displacements)
    )
    builder = _separated(n, law)
    assert builder.template() == prefix
    positions = []
    for bits, row in zip(rows, builder.rows, strict=True):
        pos, marked = _prefix_state(_instantiate(prefix, bits))
        modeled = frozenset(
            index - 3 for index in range(row.tape.bit_length()) if row.tape >> index & 1
        )
        assert (row.pos, modeled, row.dead) == (pos, marked, False), (n, law, bits)
        positions.append(pos)
    assert len(set(positions)) == 2**n
    assert all(pos % 2 for pos in positions)


@pytest.mark.medium
@pytest.mark.parametrize(
    "table",
    [format(value, f"0{2**n}b") for n in (1, 2, 3) for value in range(2 ** (2**n))],
)
def test_every_law_candidate_executes_every_table(table: str) -> None:
    n = len(table).bit_length() - 1
    for law in range(len(_LAWS[n])):
        template = _construct_small(table, n, law)
        for row, expected in enumerate(table):
            bits = format(row, f"0{n}b")
            machine = _Machine(_instantiate(template, bits), ScriptedIO())
            seen = set()
            for _ in range(100000):
                if machine.halted or machine.state in seen:
                    break
                seen.add(machine.state)
                machine.step()
            else:
                raise AssertionError((table, law, bits, "undecided execution"))
            assert ("0" if machine.halted else "1") == expected, (table, law, bits)
            assert machine.io.position() == 0
