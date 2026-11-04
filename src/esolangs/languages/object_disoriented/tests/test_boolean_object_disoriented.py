"""Tests for the Object disoriented Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.medium
@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_native_constants()
    from esolangs.languages.object_disoriented.interpreter import run

    n = len(table).bit_length() - 1

    program = esolangs.generate("Object disoriented", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Object disoriented", bits)
        io = ReadFirstIO(stdin + "Q", expected=n)
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        assert io.input_token() == "Q"
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Object disoriented", got) == table[row], (
            table,
            row,
        )


def _check_native_constants() -> None:
    from esolangs.languages.object_disoriented.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "Object disoriented", bit * (1 << n), **options
                )
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Object disoriented", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= 16 * n + 28
                    assert steps == 16 * n + 28
                    assert written.bits == 48 + 2 * n.bit_length()
                    assert io.getvalue() == bit
                    assert io.input_char() == ord("Q")

    from itertools import islice

    from esolangs.languages.object_disoriented.generator import _NAME_CHARS, _names

    base = len(_NAME_CHARS)
    rank = sum(
        _NAME_CHARS.index(char) * base ** (3 - i) for i, char in enumerate("main")
    )
    before = sum(base**size for size in (1, 2, 3)) + rank - 1
    assert list(islice(_names(), before, before + 2)) == ["maim", "maio"]

    assert (
        sum(
            len(esolangs.generate("Object disoriented", f"{v:08b}")) for v in range(256)
        )
        == 48562
    )
