"""Covers :mod:`esolangs.languages.cvnc.generator`."""

import importlib
import random

import pytest

from esolangs.generation.helpers import in_input_order
from esolangs.languages.cvnc import generator as boolean
from esolangs.languages.cvnc.generator import _direct
from esolangs.runtime.io import ScriptedIO
from tests.generators.boolean_runners import _runner, assert_runner_rows
from tests.generators.sample_tables import five_input_sample
from tests.support.generator_support import assert_constant_roots
from tests.support.witness_tables import parity, witnesses

run_cvnc = _runner("cvnc", newline=True)


def _leaves(program: str) -> int:
    """Count the leaves: every one of them ends with the ``j`` that halts."""
    return program.count("j") - program.count("ɰ̊")


def _branches(program: str) -> int:
    """Count the interior nodes: a plain ``ɰ``, not the prologue's ``ɰ̊``."""
    return program.count("\u0270") - program.count("\u0270\u030a")


class TestCvnc:
    def test_a_table_that_folds_nothing_is_a_full_tree(self) -> None:
        """Parity folds nowhere, so its plain tree keeps a leaf per row."""
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        tree = module._render(module._tree("01101001"))
        assert _leaves(tree) == 8  # one leaf per row
        assert _branches(tree) == 7  # one branch per interior node
        program = boolean.cvnc("01101001")
        assert (_leaves(program), _branches(program)) == (8, 7)

    def test_a_constant_table_folds_to_one_leaf_but_keeps_its_reads(self) -> None:
        """Folding drops the branches, never the reads."""
        _check_constants()
        for table in ("00000000", "11111111"):
            program = boolean.cvnc(table)
            assert program.count("s") == 3  # still three inputs consumed
            assert _branches(program) == 0  # nothing left to branch on
            assert _leaves(program) == 0  # root constants fall off after output

    def test_a_one_dependency_table_costs_two_leaves(self) -> None:
        """Depending on one input collapses the other two levels."""
        program = boolean.cvnc("11110000")
        assert _leaves(program) == 2
        assert _branches(program) == 1  # only the root still branches
        assert program.count("s") == 5  # the root's, then two owed on each arm
        assert_runner_rows(run_cvnc, program, "11110000")

    def test_folding_shortens_the_program(self) -> None:
        assert len(boolean.cvnc("00000000")) < len(boolean.cvnc("01101001"))

    @pytest.mark.parametrize("n", [1, 2, 3, 8, 12])
    def test_exit_jumps_to_the_final_syllable(self, n: int) -> None:
        from esolangs.languages.cvnc.interpreter import _Machine

        table = f"{random.Random(7).getrandbits(1 << n):0{1 << n}b}"
        source = boolean.cvnc(table)
        for row in (0, 1, len(table) // 2, len(table) - 1):
            io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\n")
            machine = _Machine(source, io)
            jumps = []
            while not machine.halted:
                if machine.tokens[machine.pointer] == "j":
                    target = machine.accumulator
                    assert 0 <= target < len(machine.starts)
                    jumps.append(target)
                machine.step()
            assert jumps[-2:] == [1, len(machine.starts) - 1]
            assert machine.pointer == len(machine.tokens)
            assert io.getvalue() == table[row]
            assert io.reads == n

    def test_a_table_folding_at_its_root_normalizes_the_last_read(self) -> None:
        """A folded root still holds an unpredictable bit."""
        program = boolean.cvnc("00")
        assert "sə" in program  # the floor rides the read's own vowel slot
        assert_runner_rows(run_cvnc, program, "00")


class TestCvncSharing:
    """A subtree already emitted at its depth is jumped into, not repeated."""

    @staticmethod
    def _totals(tables: list[str]) -> tuple[int, int]:
        """Return plain and shipped character totals."""
        before = after = 0
        for table in tables:
            body = in_input_order(table, _direct)
            width = (len(body) + 64).bit_length() + 1
            plain = 8 * width + 10 + len(body)
            shipped = len(boolean.cvnc(table))
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """Pin sharing with the fixed-width exit included."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (30_682, 29_979)

    def test_five_input_sample_total(self) -> None:
        """Pin five-input sharing with the fixed-width exit included."""
        assert self._totals(five_input_sample()) == (57_026, 56_077)

    def test_the_climb_is_a_closed_form(self) -> None:
        """A target is its nearer square's root climbed to, squared, stepped."""
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        climb = module._climb
        assert climb(1, 9) == [("i", 2), ("æ", 1), ("i", 0)]
        # 0, 2, 4, 16, 15: four squared is nearer fifteen than three squared.
        assert climb(0, 15) == [("i", 2), ("æ", 1), ("i", 0), ("æ", 1), ("ə", 1)]
        for start in (0, 1):
            for target in range(2, 400):
                value = start
                for step, count in climb(start, target):
                    for _ in range(count):
                        value = {"i": value + 1, "æ": value * value}.get(
                            step, max(value - 1, 0)
                        )
                assert value == target

    @pytest.mark.parametrize("n", [4, 5, 6])
    def test_a_shared_copy_runs_from_every_arm(self, n: int) -> None:
        """Seeded tables that share run every row, entered from each arm."""
        rng = random.Random(n)
        tables = [parity(n), *(f"{rng.getrandbits(2**n):0{2**n}b}" for _ in range(3))]
        for table in tables:
            program = boolean.cvnc(table)
            plain = in_input_order(table, _direct)
            if table == tables[0]:
                assert not program[:-2].endswith(plain)
            assert_runner_rows(run_cvnc, program, table)


@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [1, 3, 11])
@pytest.mark.medium
def test_lf_wrapped_generators_execute_every_small_table(n: int, width: int) -> None:
    for table in witnesses(n):
        raw = boolean.cvnc(table)
        wrapped = "\n".join(raw[at : at + width] for at in range(0, len(raw), width))
        assert_runner_rows(run_cvnc, wrapped, table)


#: A pair spelled alone, by its two bits: constants fold to a read and a leaf.
_PAIR_CHARS = {"00": 5, "01": 11, "10": 12, "11": 7}


def _closed(table: str) -> int:
    """Spell each node as a whole chunk: 5 a node over its halves, 12 a pair."""
    k = len(table).bit_length() - 1
    if len(set(table)) == 1:
        return 2 * k + 5  # k reads at 2, then the leaf
    if k == 1:
        return _PAIR_CHARS[table]
    half = len(table) // 2
    return 5 + _closed(table[:half]) + _closed(table[half:])


class TestCvncScalingBound:
    """Sharing's segment breaks and jumps never beat the chunk spelling."""

    def test_pair_chars_are_what_the_generator_spells(self) -> None:
        module = importlib.import_module("esolangs.languages.cvnc.generator")
        for table, chars in _PAIR_CHARS.items():
            assert len(module._render(module._tree(table))) == chars

    def test_a_program_is_at_most_its_prologue_and_chunks(self) -> None:
        """Price an unshared spelling plus the fixed-width exit."""
        rng = random.Random(7)
        tables = [format(v, "08b") for v in range(256)]
        tables += [
            "".join("1" if rng.random() < 0.1 + k / 70 else "0" for _ in range(64))
            for k in range(60)
        ]
        for table in tables:
            n = len(table).bit_length() - 1
            chunks = _closed(table)
            width = (chunks + 64).bit_length() + 1
            assert len(boolean.cvnc(table)) <= 8 * width + 10 + chunks, table
            assert chunks <= 17 * 2 ** (n - 1) - 5


def _check_constants() -> None:
    from esolangs.languages.cvnc.interpreter import run

    assert_constant_roots("CV(N)(C)", run, token=True)
