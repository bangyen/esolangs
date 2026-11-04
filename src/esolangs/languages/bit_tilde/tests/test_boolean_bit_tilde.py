"""bit_tilde generator tests."""

import pytest

from esolangs.languages import generators as boolean
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_parity_at_most_doubles, measure_run


class TestBitTilde:
    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        # The prologue paints the table and walks to the top of it, so the
        # opening is moves and flips -- no loop, read or print among them.
        assert set(program[: program.index(")")]) <= {">", "~"}
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.bit_tilde, (7, 8), 255)


@pytest.mark.medium
@pytest.mark.parametrize("bit", "01")
def test_every_constant_row_within_written_state_bound(bit: str) -> None:
    import esolangs
    from esolangs.languages.bit_tilde.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate("bit~", bit * (1 << n), **options)
            commands = n + 17 + 9 * int(bit)
            # Tape through cell 18/22, four pointer bits, cursor and input.
            workspace = 23 + 4 * int(bit) + commands.bit_length() + n.bit_length()
            for row in range(1 << n) if n in (1, 2, 3, 8) else (0, 1, (1 << n) - 1):
                stdin = esolangs.encode_inputs("bit~", list(map(int, f"{row:0{n}b}")))
                io = ReadFirstIO(stdin + "Q", expected=n)
                machine = _Machine("".join(program.split()), io)
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
    assert sum(len(boolean.bit_tilde(format(v, "08b"))) for v in range(256)) == 46372
    if bit == "0":
        _check_split_inputs()


def test_xor_window_scratch_read_comes_back_eight() -> None:
    """An ignored input is read into a scratch window eight cells over.

    The excursion goes out eight and must come back eight:
    coming back nine leaves the pointer a cell left of the
    window, the fix-up plants land a cell off, and the program
    walks off the tape.  Each table below is affine with an
    ignored input, so the xor-window form is the shipped one.
    """
    from tests.generators.boolean_runners import _runner

    run = _runner("bit_tilde")
    for table in ("0011", "1100", "10100101"):
        n = len(table).bit_length() - 1
        program = boolean.bit_tilde(table)
        for row in range(1 << n):
            bits = list(f"{row:0{n}b}")
            assert run(program, bits) == table[row]


def _check_split_inputs() -> None:
    import esolangs
    from esolangs.languages.bit_tilde.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    # First-bit exits and odd/even ignored prefixes, including before planting.
    for n, used in ((5, list(range(5))), (6, [1, 2, 3, 4, 5]), (7, [2, 3, 4, 5, 6])):
        table = "".join(
            str(int(all((row >> (n - 1 - i)) & 1 for i in used)))
            for row in range(1 << n)
        )
        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate("bit~", table, **options)
            for row in (0, (1 << n) // 3, (1 << n) - 1):
                io = ScriptedIO(f"{row:0{n}b}Q")
                machine = _Machine("".join(program.split()), io)
                while not machine.halted:
                    machine.step()
                assert io.getvalue() == table[row]
                assert io.reads == n
                assert io.past_end == 0
                assert io.input_char() == ord("Q")
    # Retain source witnesses 6/8 when the ledger's default span moves to 4/6.
    for n, expected_steps, expected_bits in (
        (4, 271, 92),
        (5, 365, 117),
        (6, 535, 166),
        (8, 1483, 458),
    ):
        quarter = 1 << (n - 2)
        e0 = [1] * (quarter - 1) + [0, 1] + [0] * (quarter - 1)
        table = "".join(f"{bit}{1 - bit}" for bit in e0)
        program = boolean.bit_tilde(table)
        assert len(program) == 3 * (1 << n) + 19 * n + 115
        io = ScriptedIO("0" * n)
        machine = _Machine(program, io)
        steps, written = measure_run(machine)
        assert steps == expected_steps
        assert written.bits == expected_bits
