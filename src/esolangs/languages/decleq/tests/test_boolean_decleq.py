"""decleq generator tests."""

import random

import pytest

from esolangs.generation.wrap import balance_program, balance_score, wrap_program
from esolangs.languages import generators as boolean
from tests.generators.boolean_runners import _runner
from tests.support.event_io import ReadFirstIO
from tests.support.witness_tables import parity as _parity
from tests.support.witness_tables import row_bits

run_decleq = _runner("decleq")


class TestDecleq:
    def test_essential_bits_share_one_pass_loop(self) -> None:
        """An essential bit is decremented once in the loop, then tested at each node.

        ``0110`` tests its second input under both halves of the first.
        """
        for table, tests in (("0110", (1, 2)), ("11110000", (1, 0, 0))):
            n = len(table).bit_length() - 1
            program = boolean.decleq(table)
            cells = [int(tok) for tok in program.split()]
            instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
            assert sum(1 for ins in instrs if ins[0] == -1) == n  # one read each
            for i in range(n):
                rc = 17 + i
                decs = sum(1 for ins in instrs if ins[0] == ins[1] == rc)
                assert decs == (1 + tests[i] if tests[i] else 0), (table, i)

    def test_constant_subtrees_fold(self) -> None:
        """A constant zero side enters its print gadget directly."""
        halves = "1" * 16 + "0" * 16
        parity = "".join(str((row).bit_count() & 1) for row in range(32))

        def outputs(table: str) -> int:
            cells = [int(tok) for tok in boolean.decleq(table).split()]
            return cells.count(-2)

        # Only the two gadgets print, and no operand can be -2 (operands are
        # addresses, read cells and the two ASCII constants), so every program
        # carries exactly two.
        _check_gadgets_and_owner_families()
        assert outputs(halves) == 2
        assert outputs(parity) == 2
        assert len(boolean.decleq(halves)) < len(boolean.decleq(parity))

    def test_size_is_linear_in_the_table(self) -> None:
        """The per-entry cost falls with arity: shared low levels stay narrow."""
        per_entry = [len(boolean.decleq(_parity(n))) / 2**n for n in (8, 10, 12)]
        assert per_entry[0] > per_entry[1] > per_entry[2]
        assert per_entry[2] < 8
        rng = random.Random(6)
        table = "".join(rng.choice("01") for _ in range(64))
        program = boolean.decleq(table)
        for combo in range(64):
            bits = [(combo >> (5 - i)) & 1 for i in range(6)]
            got = run_decleq(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_folded_tables_still_print_correctly(self) -> None:
        """Every folded table still prints its entry for every input."""
        for table in ("11111111", "11110000", "11001100", "00001111"):
            program = boolean.decleq(table)
            n = len(table).bit_length() - 1
            for combo in range(2**n):
                bits = row_bits(combo, n)
                got = run_decleq(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_a_repeated_subtree_is_emitted_once(self) -> None:
        """Two equal quarters share one copy and still print every entry."""
        rng = random.Random(8)
        block, other = ("".join(rng.choice("01") for _ in range(64)) for _ in "ab")
        table = block + other + block + block
        program = boolean.decleq(table)
        assert len(program) < 0.9 * len(
            boolean.decleq(block + other + other[::-1] + block[::-1])
        )
        for combo in rng.sample(range(256), 48):
            bits = [(combo >> (7 - i)) & 1 for i in range(8)]
            assert run_decleq(program, [str(b) for b in bits]) == table[combo]

    def test_untaken_jumps_target_zero(self) -> None:
        """A jump no run can take is spelt ``0``; I/O targets the next address.

        I/O falls through here but jumps to ``c`` in SUBBIG's reading.
        """
        cells = [int(tok) for tok in boolean.decleq("01101001").split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        io = [(3 * i, c) for i, (a, _b, c) in enumerate(instrs) if a in (-1, -2)]
        assert io == [(3, 6), (9, 12), (21, 24), (24, 27), (27, 30)]
        for rc in (17, 18, 19):  # each loop decrement
            assert instrs.count([rc, rc, 0]) == 1


def test_mixed_digit_operands_share_one_grid_cell() -> None:
    # All three subleq OISCs share wrap_grid, so the language is not an axis.
    language = "decleq"
    for count in range(3, 65):
        program = " ".join(("1", "22", "333")[index % 3] for index in range(count))
        balanced = balance_program(program, language)
        optimum = min(
            [program]
            + [
                wrap_program(program, language, width)
                for width in range(1, len(program) + 1)
            ],
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)
        assert balanced.split() == program.split()


@pytest.mark.parametrize("width", [0, -1])
def test_nonpositive_width_does_not_wrap(width: int) -> None:
    assert wrap_program("a b c", "decleq", width) == "a b c"


def test_multiline_source_is_untouched() -> None:
    program = "line one\nline two"
    assert wrap_program(program, "decleq", 4) == program


@pytest.mark.medium
def test_constants_reuse_scratch_and_print_after_every_read() -> None:
    import esolangs
    from esolangs.languages.decleq.interpreter import _Machine
    from esolangs.languages.decleq.proof_formulas import workspace
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Decleq", bit * (1 << n), **options)
                cells = list(map(int, program.split()))
                assert len(cells) == 3 * n + 9
                assert all(
                    cells[3 * i : 3 * i + 3] == [-1, 3 * n + 7, 3 * i + 3]
                    for i in range(n)
                )
                assert cells[3 * n : 3 * n + 3] == [-2, 3 * n + 6, 3 * n + 3]
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs("Decleq", row_bits(row, n))
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= n + 2
                    assert steps == n + 2
                    assert written.bits == workspace(n, program)
                    assert io.getvalue() == bit
                    assert io.input_char() == ord("Q")
    assert sum(len(boolean.decleq(format(v, "08b"))) for v in range(256)) == 42228


def _check_gadgets_and_owner_families() -> None:
    from esolangs.languages.decleq.generator import _owner_family
    from esolangs.languages.decleq.interpreter import _Machine
    from esolangs.languages.decleq.proof_formulas import workspace
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    cells = list(map(int, boolean.decleq("01").split()))
    tree = cells[2] + 12  # one read, one normalization and its two controls
    assert cells[tree : tree + 3] == [17, 17, 3]
    cases = ["00010100"]
    for n, threshold, admitted in ((7, 4, True), (8, 6, True), (8, 7, False)):
        table = "".join(str(int(row.bit_count() >= threshold)) for row in range(1 << n))
        assert _owner_family(table, n) == admitted
        cases.extend((table, table.translate(str.maketrans("01", "10"))))
    parity = _parity(7)
    assert not _owner_family(parity, 7)
    cases.append(parity)
    for table in cases:
        n = len(table).bit_length() - 1
        program = boolean.decleq(table)
        for row in (0, (1 << n) // 3, (1 << n) - 1):
            io = ScriptedIO(f"{row:0{n}b}Q")
            machine = _Machine(program, io)
            written = WrittenState(machine.snapshot())
            while not machine.halted:
                if machine.pc in (3, 9):
                    memory = machine.state[1]
                    assert memory[0] < 0
                    assert memory[15:17] == (48, 49)
                    assert io.reads == n
                machine.step()
                written.sample(machine.snapshot())
            assert written.bits == workspace(n, program)
            assert io.getvalue() == table[row]
            assert io.past_end == 0
            assert io.input_char() == ord("Q")
