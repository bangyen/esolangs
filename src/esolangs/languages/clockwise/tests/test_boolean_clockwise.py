"""Covers :mod:`esolangs.languages.clockwise.generator`."""

import pytest

from esolangs.languages import generators as boolean
from tests.support.witness_tables import parity, row_bits, witnesses


def run_clockwise(program: str, inputs: list[str] | list[int]) -> str:
    import esolangs

    # Clockwise loads the complete character stream (7 bits per char).
    return esolangs.run("Clockwise", program, stdin="".join(map(str, inputs)))


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_ring_reads_and_prints_without_a_lookup(n: int, bit: str) -> None:
    from esolangs.languages.clockwise.generator import _balance

    table = bit * (1 << n)
    default = boolean.clockwise(table)
    for program in (default, boolean.clockwise(table, 1), _balance(table, default)):
        assert program.count(".") == 7 * n
        assert "!" not in program
        for row in range(1 << n):
            assert run_clockwise(program, row_bits(row, n)) == bit


@pytest.mark.parametrize(
    ("table", "size"),
    [("00", 35), ("11", 39), ("01", 39), ("0011", 59), ("00001111", 97)],
)
def test_balanced_ring_for_at_most_one_input_has_the_square_size(
    table: str, size: int
) -> None:
    import esolangs

    program = str(esolangs.generate("clockwise", table, balance=True))
    assert len(program) == size
    n = len(table).bit_length() - 1
    for row in range(1 << n):
        assert run_clockwise(program, row_bits(row, n)) == table[row]


@pytest.mark.parametrize("width", [None, 1, 20])
def test_trailing_inputs_are_read_after_the_two_entry_lookup(width: int | None) -> None:
    table = "0" * 128 + "1" * 128
    program = boolean.clockwise(table, width)
    assert program.count(".") == 56
    assert len(program) < 1000
    for row in range(256):
        assert run_clockwise(program, row_bits(row, 8)) == table[row]


@pytest.mark.parametrize("width", [None, 1, 20])
def test_return_reads_complete_exactly_one_rotation(width: int | None) -> None:
    from esolangs.languages.clockwise.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    n = 8
    table = "".join(str(((row >> 7) ^ (row >> 6)) & 1) for row in range(256))
    program = boolean.clockwise(table, width)
    for row in range(256):
        io = ScriptedIO("".join(map(str, row_bits(row, n))))
        machine = _Machine(program.splitlines(), io)
        initial = machine.inp
        reads = 0
        steps = 0
        while not machine.halted:
            y, x = machine.state[:2]
            reads += machine.code[y][x] == "."
            machine.step()
            steps += 1
            assert steps < 100_000
        assert reads == 7 * n
        assert machine.inp == initial
        assert io.getvalue() == table[row]


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
        from esolangs.languages.clockwise.interpreter import _Machine
        from esolangs.runtime.io import IO

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
        """Six band rows over a doubling chain laid flat: both linear, so size is."""
        sizes = [len(boolean.clockwise(parity(n))) for n in (5, 7, 9)]
        rise = (sizes[2] - sizes[1]) / (sizes[1] - sizes[0])
        assert 3.5 < rise < 4.4, sizes
        assert sizes[2] / 2**9 < 30, sizes


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
    from esolangs.languages.clockwise.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    machine = _Machine(["R", "R"], ScriptedIO(""))
    machine.step()
    machine.step()
    with pytest.raises(ValueError, match="ring is not closed"):
        machine.step()


@pytest.mark.parametrize("split", [1, 2, 3])
def test_banded_lookup_selects_a_strip_by_the_first_inputs(split: int) -> None:
    from esolangs.languages.clockwise.generator import _clockwise_banded
    from esolangs.runtime._evaluate import _evaluate

    # The second input is ignored and the sixth trails: a head reads past
    # one and the rail reads the other.
    table = "".join(
        str((i >> 5) ^ (i >> 3) & 1 ^ (i >> 1) & (i >> 2) & 1) for i in range(64)
    )
    program = _clockwise_banded(table, split)
    assert _evaluate("Clockwise", program, inputs=6) == table
    # A positive control: dropping one entry's + flips that row alone.
    lines = program.splitlines()
    row, col = next(
        (r, c)
        for r, line in enumerate(lines)
        for c, ch in enumerate(line)
        if ch == "+" and lines[r - 1][c] == "!"
    )
    lines[row] = lines[row][:col] + " " + lines[row][col + 1 :]
    assert _evaluate("Clockwise", "\n".join(lines), inputs=6) != table


def test_balance_bands_a_random_table() -> None:
    import esolangs
    from esolangs.generation.wrap import balance_score

    table = "".join(str((value * 73 + value // 3) & 1) for value in range(64))
    balanced = esolangs.generate("Clockwise", table, balance=True)
    # 184 columns by default; two selected strips of sixteen entries each.
    assert (
        balance_score(balanced)[0]
        < 120
        < balance_score(esolangs.generate("Clockwise", table))[0]
    )


@pytest.mark.medium
def test_balance_split_rule_matches_the_split_search() -> None:
    """Oracle: the {k//3, k//3+1} contest is no wider than scanning every split."""
    import random

    from esolangs.generation.helpers import essential_inputs
    from esolangs.generation.wrap import balance_score
    from esolangs.languages.clockwise.generator import (
        _balance,
        _clockwise_banded,
        clockwise,
    )

    rng = random.Random(5)
    for n in (4, 5, 6, 7, 8):
        table = format(rng.getrandbits(1 << n), f"0{1 << n}b")
        k = len(essential_inputs(table, n))
        searched = min(
            (_clockwise_banded(table, s) for s in range(1, k)), key=balance_score
        )
        rule = _balance(table, clockwise(table))
        assert balance_score(rule)[0] <= balance_score(searched)[0]
