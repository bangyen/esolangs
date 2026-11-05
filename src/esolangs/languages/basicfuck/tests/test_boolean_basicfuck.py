"""Tests for the Basicfuck Boolean generator."""

import pytest

import esolangs
from esolangs import compat, run
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize(
    "table",
    [
        *TABLES,
        "00010111",
        "01101001",
        "11101000",
        # Parity arithmetic and a repeated-block table using shared flags.
        "0110100110010110",
        "1011010001001011",
        "01101001" * 4,
    ],
)
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    assert_every_row("Basicfuck", table)


@pytest.mark.medium
def test_constant_reads_precede_output_and_preserve_the_next_character() -> None:
    from esolangs.languages.basicfuck.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            commands = n + 2
            workspace = 12 + (n + 2).bit_length() + n.bit_length()
            for options in ({}, {"width": 1}, {"balance": True}):
                program = compat.generate("Basicfuck", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 8 * n + 48
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Basicfuck", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= commands
                    assert steps == commands
                    assert written.bits == workspace
                    assert io.getvalue() == bit
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(compat.generate("Basicfuck", format(v, "08b"))) for v in range(256))
        == 38742
    )


@pytest.mark.medium
def test_parity_does_not_depend_on_the_tree_flag_budget() -> None:
    for n in (1, 2, 3, 7, 8, 20):
        from esolangs.languages.basicfuck.interpreter import _Machine
        from tests.support.generator_support import measure_run

        parity = "".join(str(row.bit_count() % 2) for row in range(1 << n))
        for bias in (0, 1):
            table = parity if not bias else parity.translate(str.maketrans("01", "10"))
            program = compat.generate("Basicfuck", table)
            assert len(program) == 13 * n + 59
            for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                io = ReadFirstIO(f"{row:0{n}b}Q", expected=n)
                machine = _Machine(program, io)
                steps, written = measure_run(machine)
                assert steps == 2 * n + 2
                assert (
                    written.bits
                    <= 6 * n + 60 + len(program).bit_length() + n.bit_length()
                )
                assert io.getvalue() == table[row]
                assert io.input_char() == ord("Q")


def test_parity_needs_both_its_modulus_and_every_input() -> None:
    from esolangs.exceptions import InputExhaustedError

    program = compat.generate("Basicfuck", "0110")
    with pytest.raises(InputExhaustedError):
        run("Basicfuck", program, stdin="0")
    broken = program.replace("48~49", "48~50")
    assert run("Basicfuck", broken, stdin="11").output != "0"


def test_projected_parity_reads_ignored_inputs_without_adding_them() -> None:
    for table in ("0011", "0101", "00111100", "01011010"):
        from esolangs.languages.basicfuck.generator import affine_form
        from esolangs.languages.basicfuck.interpreter import _Machine
        from tests.support.generator_support import measure_run

        n = len(table).bit_length() - 1
        form = affine_form(table, n)
        assert form is not None
        m = sum(form[1])
        source = compat.generate("Basicfuck", table)
        assert len(source) == 8 * n + 5 * m + 59
        for row, expected in enumerate(table):
            io = ReadFirstIO(f"{row:0{n}b}Q", expected=n)
            steps, _ = measure_run(_Machine(source, io))
            assert steps == n + m + 2
            assert io.getvalue() == expected
            assert io.input_char() == ord("Q")
