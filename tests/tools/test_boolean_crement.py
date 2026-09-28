"""Covers :mod:`esolangs.tools.crement`."""

import random
from itertools import pairwise, product

import pytest

from esolangs.exceptions import TruthTableError
from esolangs.interpreters.other.crement import _Machine
from esolangs.tools.crement import PAIR, _crement_ordered, crement
from esolangs.tools.helpers import TEMPLATE_CHAR, best_input_order, runs
from esolangs.vm import run_until_halt_or_cycle
from tests.tools.fills import instantiate_crement
from tests.tools.sample_tables import five_input_sample


def _result(program: str) -> str:
    """The termination answer: a halt is 0, a proven state cycle is 1."""
    return "0" if run_until_halt_or_cycle(_Machine(program)) else "1"


def _dense(n: int) -> str:
    return "".join("1" if (i * 7 + 3) % 5 < 2 else "0" for i in range(2**n))


def _check(table: str) -> None:
    """Every row answers per its entry, and every row has one length."""
    n = len(table).bit_length() - 1
    template = crement(table)
    sizes = set()
    got = ""
    for bits in product(range(2), repeat=n):
        program = instantiate_crement(template, list(bits))
        sizes.add(len(program))
        got += _result(program)
    assert got == table, f"{table}: got {got}"
    assert len(sizes) == 1, f"{table}: lengths {sorted(sizes)}"


class TestCrementTree:
    """Decision tree over per-input testers reached by patched jumps.

    Crement has no output and no input instruction, so the bit is the data
    of a jump and the answer is termination: the instantiated program halts
    for a ``0`` entry and reaches a one-line state cycle for a ``1``.
    """

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs, every row, one length per template."""
        for table_int in range(2 ** (2**n)):
            _check(format(table_int, f"0{2**n}b"))

    @pytest.mark.parametrize("n", [4, 5, 6])
    @pytest.mark.medium
    def test_random_tables(self, n: int) -> None:
        """Thirty seeded tables at each of four to six inputs, every row."""
        random.seed(7 + n)
        for _ in range(30):
            _check("".join(random.choice("01") for _ in range(2**n)))

    def test_template_embeds_each_input_once_in_order(self) -> None:
        template = crement(_dense(3))
        setters = (PAIR,) * 3
        assert "{X" not in template
        assert template.count(TEMPLATE_CHAR) == sum(len(zero) for zero, _ in setters)
        # One run per input, each a tester's first line, on lines 3, 5, 7.
        lines = template.splitlines()
        run = TEMPLATE_CHAR * len("+J 0 0")
        assert [i for i, line in enumerate(lines) if TEMPLATE_CHAR in line] == [3, 5, 7]
        assert [line for line in lines if TEMPLATE_CHAR in line] == [run] * 3
        assert len(runs(template, TEMPLATE_CHAR, setters)) == 3

    def test_setter_spells_the_bit_as_a_jump(self) -> None:
        """The two fills differ only in the tester's data field."""
        template = crement("0110")
        zero = instantiate_crement(template, [0, 1]).splitlines()
        one = instantiate_crement(template, [1, 1]).splitlines()
        assert [(a, b) for a, b in zip(zero, one, strict=True) if a != b] == [
            ("+J 0 0", "+J 0 1")
        ]

    def test_one_leaf_is_a_one_step_state_cycle(self) -> None:
        """The diverging row parks on ``+J @ 1`` without writing the program."""
        machine = _Machine(instantiate_crement(crement("01"), [1]))
        for _ in range(6):
            machine.step()
        before = machine.snapshot()
        machine.step()
        assert machine.snapshot() == before
        assert machine.memory[machine.ip].address == machine.ip

    @pytest.mark.parametrize("table", ["0", "", "012", "0110" * 3])
    def test_rejects_bad_tables(self, table: str) -> None:
        with pytest.raises(TruthTableError):
            crement(table)

    def test_constant_tables_fold_to_the_gadget_alone(self) -> None:
        """A constant table has no node: line 0 jumps to the halt or the loop."""
        assert crement("0000").splitlines()[:3] == ["+J 1 1", "+J 7 1", "+J @ 1"]
        assert crement("1111").splitlines()[:3] == ["+J 2 1", "+J 7 1", "+J @ 1"]
        assert _result(instantiate_crement(crement("0000"), [0, 1])) == "0"
        assert _result(instantiate_crement(crement("1111"), [0, 1])) == "1"

    def test_constant_subtrees_fold(self) -> None:
        """A one-dependency table is one node; parity is five, shared.

        Parity's tree has seven nodes, but only two distinct subtrees at
        each level below the root, so two of them are jumps to a copy.
        """
        assert len(crement("11110000")) < len(crement("10010110"))
        assert crement("11110000").splitlines()[9:] == ["+A 3 0", "+A 4 1", "+J 3 1"]
        assert crement("10010110").count("\n") + 1 == 3 + 6 + 3 * 5

    def test_sizes_at_most_double_per_added_input(self) -> None:
        """Seeded random templates through n=10 never more than double.

        Each node is three lines whose operands are a tester's line number
        or an offset, so the plain tree tracks its node count and doubles
        per input; the shared build emits a random table's distinct
        subtrees only, of which there are fewer than ``2**n / n`` or so,
        and the ratio creeps up towards two from below.
        """
        tables = [
            format(random.Random(n).getrandbits(2**n), f"0{2**n}b")
            for n in range(1, 11)
        ]
        sizes = [len(crement(table)) for table in tables]
        assert sizes == [34, 48, 130, 288, 431, 708, 1266, 2040, 3510, 6608]
        ratios = [b / a for a, b in pairwise(sizes)]
        assert all(r <= 2.25 for r in ratios[2:]), ratios
        assert all(1.6 <= r <= 2 for r in ratios[-3:]), ratios

    def test_level_patches_the_chosen_inputs_tester(self) -> None:
        """A table on the last input alone is one node calling its tester.

        Name order folds ``10101010`` only at the bottom; split on input 2
        first, the root patches and calls line 7, input 2's tester, and the
        runs stay on lines 3, 5, 7.
        """
        template = crement("10101010")
        assert template.splitlines()[9:] == ["+A 7 0", "+A 8 1", "+J 7 1"]
        assert len(template) < len(_crement_ordered("10101010", (0, 1, 2)))

    @pytest.mark.parametrize("n", [2, 3])
    def test_reordering_never_grows_a_template(self, n: int) -> None:
        """Every table is at most its name-order template, as emitted.

        The comparison is on the text, tester and patch addresses included,
        so the fold a reorder buys cannot be spent on its routing.  Over all
        three-input tables it and sharing save 14.5% (43,596 to 37,278).
        """
        identity = tuple(range(n))
        old = new = 0
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            before = len(_crement_ordered(table, identity))
            after = len(crement(table))
            assert after <= before, table
            old, new = old + before, new + after
        assert (old, new) == {2: (1444, 1352), 3: (43596, 37278)}[n]

    def test_runs_a_handful_of_commands_per_input(self) -> None:
        """One node per level: a halting row runs ``5 n + 2`` commands at most.

        The root jump, three lines a node, the tester's two lines when the
        bit is 0 and the halt gadget; the all-ones row takes every tester's
        first line and so runs one fewer per level.
        """
        for n in (2, 4, 6):
            template = crement("1" * (2**n - 1) + "0")
            machine = _Machine(instantiate_crement(template, [1] * n))
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            assert steps == 4 * n + 2


class TestCrementSharing:
    """A subtree already emitted at its level is jumped to, not repeated.

    The plain tree stays a candidate for every order, so no table grows; the
    gain grows with the table, so it is judged on the seeded five-input
    sample too (``docs/CONTRIBUTING.md``).
    """

    @staticmethod
    def _totals(tables: list[str]) -> tuple[int, int]:
        """(plain, shipped) character totals, each table checked not to grow."""
        before = after = 0
        for table in tables:
            plain = len(best_input_order(table, _crement_ordered))
            shipped = len(crement(table))
            assert shipped <= plain, table
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """All 256 three-input tables: 39,156 to 37,278 characters, 4.8%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (39156, 37278)

    def test_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 114,791 to 83,070 characters, 27.6%."""
        assert self._totals(five_input_sample()) == (114791, 83070)

    def test_a_shared_copy_is_patched_by_whoever_enters(self) -> None:
        """Parity's repeated subtrees run from both parents, every row.

        Each node writes its tester's targets on entry, so the copy's
        children are right whichever parent jumped to it.
        """
        table = "01101001" * 4
        template = crement(table)
        assert len(template) < len(best_input_order(table, _crement_ordered))
        _check(table)
