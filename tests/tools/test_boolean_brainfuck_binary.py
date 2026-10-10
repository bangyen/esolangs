"""Native controls for four-bit residual banks and their admission prices."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.tools.brainfuck import _bf_ordered, bf_tree
from esolangs.tools.brainfuck_binary import binary_bank
from scripts.benchmark import WrittenState


def _execute(table: str, program: str, rows: range | list[int], bound: int) -> int:
    n = len(table).bit_length() - 1
    workspace = (
        2 * n + 6 + (2 * n).bit_length() + n.bit_length() + len(program).bit_length()
    )
    machine = _Machine(program, ScriptedIO(""))
    maximum = 0
    for row in rows:
        machine.state = (0, 0, (0,), 0, False)
        machine.io = ScriptedIO(f"{row:0{n}b}")
        written = WrittenState(machine.snapshot())
        commands = 0
        while not machine.halted and commands <= bound:
            machine.step()
            written.sample(machine.snapshot())
            commands += 1
        assert machine.halted
        assert machine.io.getvalue() == table[row]
        assert machine.io.progress() == n
        assert commands <= bound
        assert written.bits <= workspace
        maximum = max(maximum, commands)
    return maximum


@pytest.mark.parametrize("table", ["0110", "0" * 64, "0000011001100000" * 4])
def test_insufficient_retired_cells_or_functions_keep_existing_paths(
    table: str,
) -> None:
    assert binary_bank(table, 100_000) is None


@pytest.mark.parametrize(
    ("words", "maximum"),
    [
        ([1, 2, 3, 4, 5, 6, 7, 8, 8, 1, 2, 3, 4, 5, 6, 7], 607),
        ([0, 0, 15, 15, 1, 2, 3, 4, 1, 2, 3, 4, 0, 0, 15, 15], 547),
    ],
)
def test_price_covers_completed_paths_and_high_labels_without_a_free_input(
    words: list[int], maximum: int
) -> None:
    table = "".join(f"{word:04b}" for word in words)
    header = ">>".join("," + "-" * 48 for _ in range(6))
    built = binary_bank(table, 100_000)
    assert built is not None
    body, commands = built
    program = header + body + "+" * 48 + "."
    assert len(header) + commands + 49 == maximum
    assert _execute(table, program, range(64), maximum) == maximum
    assert binary_bank(table, 69 * 6 + 44 - len(header) - 49) is None


@pytest.mark.parametrize("words", [[1, 7, 7, 1], [0, 1, 7, 0, 7, 1, 1, 7]])
def test_narrow_words_consume_fixed_one_digits_and_completed_zero_paths(
    words: list[int],
) -> None:
    table = "".join(f"{word:04b}" for word in words)
    n = len(table).bit_length() - 1
    header = ">>".join("," + "-" * 48 for _ in range(n))
    built = binary_bank(table, 100_000)
    assert built is not None
    body, commands = built
    _execute(
        table,
        header + body + "+" * 48 + ".",
        range(1 << n),
        len(header) + commands + 49,
    )


@pytest.mark.medium
@pytest.mark.parametrize("n", [14, 16])
@pytest.mark.parametrize("seed", [73017, 73018, 73019])
@pytest.mark.parametrize("start", range(0, 1024, 128))
def test_fourteen_class_cap_bank_executes_every_essential_row(
    seed: int, start: int, n: int
) -> None:
    rng = random.Random(seed)
    core = "".join(f"{rng.randrange(1, 15):04b}" for _ in range(256))
    ignored = n - 10
    table = core * (1 << ignored)
    header = ">" * (2 * ignored) + "," * (ignored + 1) + "-" * 48
    header += (">>," + "-" * 48) * 9
    built = binary_bank(table, 69 * n + 44 - len(header) - 49)
    assert built is not None
    body, commands = built
    program = header + body + "+" * 48 + "."
    assert bf_tree(table) == program
    assert len(program) < len(_bf_ordered(table, tuple(range(n)), bank=False))
    _execute(
        table,
        program,
        [
            row | padding
            for row in range(start, start + 128)
            for padding in (0, ((1 << ignored) - 1) << 10)
        ],
        len(header) + commands + 49,
    )
