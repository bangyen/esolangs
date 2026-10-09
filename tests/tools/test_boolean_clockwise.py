"""Covers :mod:`esolangs.tools.clockwise`."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_clockwise,
)
from tests.witness_tables import parity, row_bits, witnesses


class TestClockwise:
    @pytest.mark.medium
    def test_the_lookup_computes_every_row_at_five_and_six_inputs(self) -> None:
        """The indexed table answers two dense five- and six-input tables."""
        for n in (5, 6):
            size = 1 << n
            tables = (
                ("01101001" * (size // 8))[:size],
                "".join(str((i * 73 + i // 3) & 1) for i in range(size)),
            )
            for table in tables:
                program = boolean.clockwise(table)
                for combo in range(size):
                    assert run_clockwise(program, row_bits(combo, n)) == table[combo]

    @pytest.mark.parametrize("width", [None, 1])
    def test_every_run_reads_each_input_exactly_once(self, width: int | None) -> None:
        """Clockwise's input queue rotates, so a run must consume 7n bits."""
        from esolangs.interpreters.grid_based.clockwise import _Machine
        from esolangs.interpreters.io import IO

        class _Quiet(IO):
            def __init__(self, text: str) -> None:
                self._text = text

            def input_all(self, _prompt: str = "Input: ") -> str:
                return self._text

            def print_char(self, char: str) -> None:
                pass

        # A constant, and a table ignoring every input after the first.
        tables = [
            (n, table)
            for n in (1, 2, 3)
            for table in (
                "01101001"[: 2**n].ljust(2**n, "1"),
                "1" * 2**n,
                "0" * 2 ** (n - 1) + "1" * 2 ** (n - 1),
            )
        ]
        for n, table in tables:
            program = boolean.clockwise(table, width)
            for combo in range(2**n):
                machine = _Machine(
                    program.splitlines(),
                    _Quiet("".join(map(str, row_bits(combo, n)))),
                )
                start = machine.inp
                steps = 0
                while not machine.halted:
                    machine.step()
                    steps += 1
                    assert steps < 100_000, "run did not close the ring"
                assert machine.inp == start, (n, combo)

    def test_size_is_linear_in_the_table(self) -> None:
        """Four table rows and a doubling chain: both linear, so size is."""
        sizes = [len(boolean.clockwise(parity(n))) for n in (5, 7, 9)]
        rise = (sizes[2] - sizes[1]) / (sizes[1] - sizes[0])
        assert 3.5 < rise < 4.4, sizes
        assert sizes[2] / 2**9 < 20, sizes


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 3, 9, 10, 11, 20, 27, 80])
def test_width_rotates_the_lookup_without_changing_answers(width: int) -> None:
    """Both lookup orientations execute every row, including floor widths."""
    import esolangs

    for n in range(1, 7):
        table = ("01101001" * 8)[: 1 << n]
        plain = boolean.clockwise(table)
        program = esolangs.generate("Clockwise", table, width=width)
        plain_width = max(map(len, plain.splitlines()))
        assert max(map(len, program.splitlines())) <= max(
            width, min(plain_width, 2 if n <= 2 else 2 * n + 5)
        )
        if plain_width <= width:
            assert program == plain
        for combo in range(1 << n):
            assert run_clockwise(program, row_bits(combo, n)) == table[combo]


def test_rotated_lookup_size_is_linear() -> None:
    """Implicit padded rails keep rotation from rendering a filled rectangle."""
    sizes = [len(boolean.clockwise(parity(n), 1)) for n in (5, 7, 9)]
    assert sizes[2] / 2**9 < 30
    assert 3.5 < (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) < 4.4


@pytest.mark.medium
def test_entry_digit_prefix_executes_every_small_table() -> None:
    """The shared six bits precede lookup without carrying an index into it."""
    assert max(map(len, boolean.clockwise("0110", 1).splitlines())) == 2
    for n in range(1, 4):
        for table in witnesses(n):
            program = boolean.clockwise(table, 1)
            for row, expected in enumerate(table):
                assert run_clockwise(program, row_bits(row, n)) == expected


def test_single_column_cannot_close_a_clockwise_ring() -> None:
    """A downward beam's next clockwise turn leaves the only column."""
    from esolangs.interpreters.grid_based.clockwise import _Machine
    from esolangs.interpreters.io import ScriptedIO

    machine = _Machine(["R", "R"], ScriptedIO(""))
    machine.step()
    machine.step()
    with pytest.raises(ValueError, match="ring is not closed"):
        machine.step()
