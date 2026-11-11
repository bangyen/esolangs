"""Covers :mod:`esolangs.languages.taglate.generator`."""

import pytest

import esolangs
from esolangs import run as execute
from esolangs.languages.taglate import generator as boolean
from esolangs.languages.taglate.generator import _seed_commands, _taglate_raw
from esolangs.languages.taglate.wrapping import _taglate
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_constant_output, constant_programs
from tests.support.witness_tables import row_bits, witnesses


def run_taglate(program: str, inputs: list[str]) -> str:

    return execute("Taglate", program, stdin="".join(inputs)).output


def test_execution_bound_is_one_form() -> None:
    from scripts.docs.resource_evidence import resource_bounds

    execution = resource_bounds("Taglate")["execution"].formula

    assert execution(4, "") == 329
    assert execution(5, "") == 484
    _check_resource_layouts()


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_every_input_before_printing(n: int, bit: str) -> None:
    from esolangs.languages.taglate.interpreter import _Machine

    if n == 1 and bit == "0":
        _check_constants()
    table = bit * (1 << n)
    programs = [
        esolangs.generate("Taglate", table, width=w).source for w in (None, 1, 20)
    ]
    programs.append(esolangs.generate("Taglate", table, balance=True).source)
    for program in programs:
        for row in range(1 << n):
            io = ScriptedIO(f"{row:0{n}b}" + "extra")
            machine = _Machine(str(program).splitlines(), io)
            for _ in range(1000):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            assert io.position() == n
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
        _check_packed_leaves()
        failures = 0
        for tt in witnesses(3):
            program = boolean.taglate(tt)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = run_taglate(program, [str(b) for b in bits])
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
            assert 8 * len(boolean.taglate(table)) < full, table

    def test_gapped_dependencies_reduce_without_reordering_inputs(self) -> None:
        """Every n=3 function of inputs 0 and 2 uses the small program."""
        assert_analysis_complement("Taglate", "read_at")
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
            assert program.count("h") == 3, table
            for combo in range(8):
                bits = [str((combo >> shift) & 1) for shift in (2, 1, 0)]
                assert run_taglate(program, bits) == table[combo], (table, bits)

    def test_three_inputs_of_five_are_built_over_three(self) -> None:
        """A dependency set of three in n=5 is built over three inputs."""
        table = "".join(bit * 4 for bit in "01101001")
        program = boolean.taglate(table)
        assert len(program) == 197
        for combo in range(32):
            bits = [str((combo >> shift) & 1) for shift in (4, 3, 2, 1, 0)]
            assert run_taglate(program, bits) == table[combo], bits

    def test_reduced_programs_still_read_every_input(self) -> None:
        """A reduced program consumes the inputs it no longer uses."""
        for n in (1, 2, 3, 4):
            for table in (
                "1" * 2**n,
                "1" * 2 ** (n - 1) + "0" * 2 ** (n - 1),
                ("10" * 2**n)[: 2**n],
            ):
                program = boolean.taglate(table)
                assert program.count("h") == n, (n, table)

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
            got = run_taglate(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"


@pytest.mark.parametrize("width", [1, 7, 19])
def test_narrow_seed_truth_tables(width: int) -> None:
    """Bootstrapping leaves the original seed and input consumption intact."""
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
            assert run_taglate(program, bits) == table[combo]
        assert boolean.taglate(table) == raw


@pytest.mark.parametrize("count", [20, 70, 262, 1030])
def test_seed_bootstrap_exact_queue(count: int) -> None:
    """Multiple URL layers initialize the exact FIFO without any input."""
    from esolangs.languages.taglate.interpreter import _advance, _match, _tokens

    seed = "1" + "0" * (count - 2) + "1"
    tokens = _tokens(_seed_commands(seed))
    match = _match(tokens)
    state = ((), 0)
    for token in tokens:
        state = _advance(state, token, match)
    assert state[0] == tuple(map(ord, seed))


def test_public_narrow_generator_route() -> None:

    program = esolangs.generate("taglate", "0110", width=1).source
    assert max(map(len, program.splitlines())) == 1
    assert run_taglate(program, ["0", "1"]) == "1"


def test_taglate_needs_a_seed_and_commands_below_it() -> None:
    assert _taglate("seed-only", 40) == "seed-only"


def _check_constants() -> None:
    from esolangs.languages.taglate.interpreter import run

    for n, bit, _options, program in constant_programs("Taglate", range(1, 13)):
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(row + "7", expected=n)
            assert_constant_output(run, program.splitlines(), io, bit, n)
            assert io.input_char() == ord("7")


def _check_packed_leaves() -> None:
    from esolangs.languages.taglate.interpreter import _Machine, run
    from esolangs.languages.taglate.proof_formulas import workspace
    from esolangs.languages.taglate.tests.ablations import ablate
    from scripts.docs.resource_evidence import resource_bounds

    execution = resource_bounds("Taglate")["execution"].formula

    totals = [0, 0]
    for value in range(256):
        table = f"{value:08b}"
        program = _taglate_raw(table)
        assert ablate(table, "default") == program
        baseline = ablate(table, "packed_leaves")
        totals[0] += len(baseline)
        totals[1] += len(program)
        for row in range(8):
            io = ScriptedIO(f"{row:03b}7")
            machine = _Machine(program.splitlines(), io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            while not machine.halted:
                assert io.getvalue() == ""
                machine.step()
                written.sample(machine.workspace_snapshot())
                steps += 1
            assert io.getvalue() == table[row]
            assert io.reads == 3
            assert io.past_end == 0
            assert steps <= execution(3, program)
            assert written.bits <= workspace(3, program)
    assert totals == [53146, 46242]
    # Reversing a leaf's low-first bit order must fail this asymmetric table.
    program = _taglate_raw("0001")
    seed, commands = program.split("\n")
    mutant = seed.replace("(", "!") + "\n" + commands
    io = ScriptedIO("00")
    run(mutant.splitlines(), io)
    assert io.getvalue() != "0"


def _check_resource_layouts() -> None:
    from esolangs.languages.taglate.interpreter import _Machine
    from esolangs.languages.taglate.proof_formulas import workspace
    from esolangs.languages.taglate.tests.formulas import resource_witness
    from scripts.docs.resource_evidence import resource_bounds

    execution = resource_bounds("Taglate")["execution"].formula

    for n in (1, 2, 3, 4, 5):
        table = resource_witness(n)
        for options in ({}, {"width": 1}, {"balance": True}):
            program = str(esolangs.generate("Taglate", table, **options).source)
            row = (1 << n) - 4 if n >= 2 else 0
            io = ScriptedIO(f"{row:0{n}b}!")
            machine = _Machine(program.splitlines(), io)
            written = WrittenState(machine.workspace_snapshot())
            bound = execution(n, program)
            steps = count_steps(machine, bound, written=written)
            assert io.getvalue() == table[row]
            assert io.reads == n
            assert io.input_char() == ord("!")
            assert written.bits <= workspace(n, program)
            if not options:
                assert steps == execution(n, program)
                assert written.bits == workspace(n, program)
