"""Covers :mod:`esolangs.tools.taglate`."""

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.tools.wrap import (
    _taglate,
)
from tests.support.witness_tables import row_bits, witnesses
from tests.tools.boolean_runners import (
    run_taglate,
)


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_the_ghost_and_real_inputs_before_printing(
    n: int, bit: str
) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.queue_based.taglate import _Machine

    table = bit * (1 << n)
    programs = [esolangs.generate("Taglate", table, width=w) for w in (None, 1, 20)]
    programs.append(esolangs.generate("Taglate", table, balance=True))
    ghost = "0" if n > 1 and n % 2 else ""
    for program in programs:
        for row in range(1 << n):
            io = ScriptedIO(ghost + f"{row:0{n}b}" + "extra")
            machine = _Machine(str(program).splitlines(), io)
            for _ in range(1000):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            assert io.position() == n + len(ghost)
            assert io.getvalue() == bit


class TestTaglate:
    def test_all_two_input_tables(self) -> None:
        """Every two-input truth table produces the right result."""
        for table in range(16):
            tt = format(table, "04b")
            for combo in range(4):
                bits = [(combo >> 1) & 1, combo & 1]
                got = run_taglate(boolean.taglate(tt), [str(b) for b in bits])
                assert got == tt[combo], f"{tt} inputs {bits}"

    @pytest.mark.medium
    def test_all_three_input_tables(self) -> None:
        """Every three-input truth table produces the right result."""
        failures = 0
        for tt in witnesses(3):
            program = boolean.taglate(tt)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                inputs = ["0"] + [str(b) for b in bits]  # ghost digit
                got = run_taglate(program, inputs)
                if got != tt[combo]:
                    failures += 1
                    if failures <= 3:
                        print(
                            f"  FAIL {tt} inputs {bits}: "
                            f"got {got!r} expected {tt[combo]!r}"
                        )
        assert failures == 0, f"{failures} failures out of 2048 combos"

    def test_tables_ignoring_inputs_shrink(self) -> None:
        """A table that ignores inputs is emitted as the smaller table."""
        full = len(boolean.taglate("10010110"))  # depends on all three
        for table in ("11110000", "11001100", "10101010", "00000000"):
            assert len(boolean.taglate(table)) < full // 10, table

    def test_gapped_dependencies_reduce_without_reordering_inputs(self) -> None:
        """Every n=3 function of inputs 0 and 2 uses the small program."""
        tables = (
            "00000101",
            "00001010",
            "01010000",
            "01011010",
            "01011111",
            "10100000",
            "10100101",
            "10101111",
            "11110101",
            "11111010",
        )
        full = len(boolean.taglate("10010110"))
        for table in tables:
            program = boolean.taglate(table)
            assert len(program) < full, table
            assert program.count("h") == 4, table  # ghost plus all three inputs
            for combo in range(8):
                bits = [str((combo >> shift) & 1) for shift in (2, 1, 0)]
                assert run_taglate(program, ["0", *bits]) == table[combo], (table, bits)

    def test_reduced_programs_still_read_every_input(self) -> None:
        """A reduced program consumes the inputs it no longer uses."""
        for n in (1, 2, 3, 4):
            expected = n + (1 if n % 2 == 1 and n > 1 else 0)
            for table in (
                "1" * 2**n,
                "1" * 2 ** (n - 1) + "0" * 2 ** (n - 1),
                ("10" * 2**n)[: 2**n],
            ):
                program = boolean.taglate(table)
                assert program.count("h") == expected, (n, table)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1111111100000000", 4),  # depends on input 0
            ("1111000011110000", 4),  # input 1
            ("1010101010101010", 4),  # input 3
            ("1111111111111111", 4),  # none at all
            # depends on inputs 0-2, so the window widens rightward to 0-3
            ("0000000000000011", 4),
            # depends on inputs 1-3, which has no room on the right, so the
            # window widens leftward to 0-3 instead
            ("0000000100000001", 4),
        ],
    )
    def test_reduced_tables_compute_past_three_inputs(self, table: str, n: int) -> None:
        """The reduction stays correct deeper than the exhaustive sweep."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = row_bits(combo, n)
            ghost = ["0"] if n % 2 == 1 and n > 1 else []
            got = run_taglate(program, ghost + [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"


@pytest.mark.parametrize("width", [1, 7, 19])
def test_narrow_seed_truth_tables(width: int) -> None:
    """Bootstrapping leaves the original seed and input consumption intact."""
    from esolangs.tools.taglate import _taglate_raw

    tables = [f"{value:02b}" for value in range(4)]
    tables += [f"{value:04b}" for value in range(16)]
    tables += ["10010110", "00000001", "0000000000000001"]
    for table in tables:
        n = (len(table) - 1).bit_length()
        program = boolean.taglate(table, width=width)
        raw = _taglate_raw(table)
        assert max(map(len, program.splitlines())) <= width
        for combo in range(len(table)):
            bits = [str((combo >> shift) & 1) for shift in range(n - 1, -1, -1)]
            ghost = ["0"] if n > 1 and n % 2 else []
            assert run_taglate(program, ghost + bits) == table[combo]
        assert boolean.taglate(table) == raw


@pytest.mark.parametrize("count", [20, 70, 262, 1030])
def test_seed_bootstrap_exact_queue(count: int) -> None:
    """Multiple URL layers initialize the exact FIFO without any input."""
    from esolangs.interpreters.queue_based.taglate import _advance, _match, _tokens
    from esolangs.tools.taglate import _seed_commands

    seed = "1" + "0" * (count - 2) + "1"
    tokens = _tokens(_seed_commands(seed))
    match = _match(tokens)
    state = ((), 0)
    for token in tokens:
        state = _advance(state, token, match)
    assert state[0] == tuple(map(ord, seed))


def test_public_narrow_generator_route() -> None:
    import esolangs

    program = esolangs.generate("taglate", "0110", width=1)
    assert max(map(len, program.splitlines())) == 1
    assert run_taglate(program, ["0", "1"]) == "1"


def test_taglate_needs_a_seed_and_commands_below_it() -> None:
    assert _taglate("seed-only", 40) == "seed-only"
