"""Tests for the Blindfolded Arithmetic Boolean generator."""

import pytest

import esolangs
from tests.support.stdin_check import _check_stdin

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Blindfolded Arithmetic", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Blindfolded Arithmetic", bits)
        got = esolangs.run("Blindfolded Arithmetic", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Blindfolded Arithmetic", got) == table[row], (
            table,
            row,
        )


def test_the_input_is_the_row_number() -> None:
    """The input must be positive, so row 0 is fed as 1."""
    assert esolangs.describe("Blindfolded Arithmetic")["input_shape"] == "row_number"
    assert esolangs.encode_inputs("Blindfolded Arithmetic", [0, 0]) == "1\n"
    assert esolangs.encode_inputs("Blindfolded Arithmetic", [1, 0]) == "3\n"
    _check_alternating_rounds()
    from esolangs.vm import make_vm
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                source = esolangs.generate(
                    "Blindfolded Arithmetic", bit * (1 << n), **options
                )
                assert len(source.replace("\n", "")) == 11
                for row in (0, 1, (1 << n) - 1):
                    vm = make_vm("Blindfolded Arithmetic", source, stdin=f"{row + 1}\n")
                    state = WrittenState(vm.snapshot())
                    steps = 0
                    while not vm.halted:
                        vm.step()
                        state.sample(vm.snapshot())
                        steps += 1
                    assert vm.output == bit
                    assert steps == 2
                    assert state.bits <= n + 8


@pytest.mark.parametrize("stdin", ["0\n", "5\n"])
def test_a_row_number_outside_one_to_t_is_refused(stdin: str) -> None:
    with pytest.raises(esolangs.ArgumentError, match=r"out of range.*\(1\.\.4\)"):
        _check_stdin("Blindfolded Arithmetic", stdin, "0110")


def _check_alternating_rounds() -> None:
    from esolangs.languages.blindfolded_arithmetic.generator import _lookup
    from esolangs.languages.blindfolded_arithmetic.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    # Both counter parities, ignored positions and complemented/mirrored answers.
    for table in (
        "0110",
        "01101001",
        "01011010",
        "00000001",
        "11111110",
        "0110100110010110",
        "1001011001101001",
    ):
        program = esolangs.generate("Blindfolded Arithmetic", table)
        for row, bit in enumerate(table):
            io = ScriptedIO(f"{row + 1} 99")
            machine = _Machine(program, io)
            for _ in range(program.count(";") + 1):
                machine.step()
            assert machine.halted
            assert machine.state[1] == len(machine.program) - 1
            assert io.getvalue() == bit
            assert io.reads == 1
            assert io.input_num() == 99
    assert _lookup(3, [0, 2]).count("c=a+a") == 1
