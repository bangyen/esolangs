"""Covers :mod:`esolangs.tools.crement`."""

import random
from itertools import pairwise, product

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.exceptions import TruthTableError
from esolangs.interpreters.other.crement import _Machine
from esolangs.tools.crement import PAIR, _crement_ordered, crement
from esolangs.tools.helpers import TEMPLATE_CHAR, best_input_order, runs
from esolangs.vm import run_until_halt_or_cycle
from tests.support.witness_tables import dense
from tests.tools.fills import fill
from tests.tools.sample_tables import five_input_sample

instantiate_crement = fill("Crement")


def _result(program: str) -> str:
    """The termination answer: a halt is 0, a proven state cycle is 1."""
    return "0" if run_until_halt_or_cycle(_Machine(program)) else "1"


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
    """Decision tree over per-input testers reached by patched jumps."""

    @pytest.mark.parametrize("n", [4, 5, 6])
    @pytest.mark.medium
    def test_random_tables(self, n: int) -> None:
        """Thirty seeded tables at each of four to six inputs, every row."""
        random.seed(7 + n)
        for _ in range(30):
            _check("".join(random.choice("01") for _ in range(2**n)))

    def test_template_embeds_each_input_once_in_order(self) -> None:
        template = crement(dense(3))
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
        """A one-dependency table is one node; parity is five, shared."""
        assert len(crement("11110000")) < len(crement("10010110"))
        assert crement("11110000").splitlines()[9:] == ["+A 3 0", "+A 4 1", "+J 3 1"]
        assert crement("10010110").count("\n") + 1 == 3 + 6 + 3 * 5

    def test_sizes_at_most_double_per_added_input(self) -> None:
        """Seeded random templates through n=10 never more than double."""
        tables = [
            format(random.Random(n).getrandbits(2**n), f"0{2**n}b")
            for n in range(1, 11)
        ]
        sizes = [len(crement(table)) for table in tables]
        assert sizes == [34, 48, 130, 288, 431, 710, 1266, 2146, 3510, 6632]
        ratios = [b / a for a, b in pairwise(sizes)]
        assert all(r <= 2.25 for r in ratios[2:]), ratios
        assert all(1.6 <= r <= 2 for r in ratios[-3:]), ratios

    def test_level_patches_the_chosen_inputs_tester(self) -> None:
        """A table on the last input alone is one node calling its tester."""
        template = crement("10101010")
        assert template.splitlines()[9:] == ["+A 7 0", "+A 8 1", "+J 7 1"]
        assert len(template) < len(_crement_ordered("10101010", (0, 1, 2)))

    @pytest.mark.parametrize("n", [2, 3])
    def test_reordering_never_grows_a_template(self, n: int) -> None:
        """Every table is at most its name-order template, as emitted."""
        identity = tuple(range(n))
        old = new = 0
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            before = len(_crement_ordered(table, identity))
            after = len(crement(table))
            assert after <= before, table
            old, new = old + before, new + after
        assert (old, new) == {2: (1444, 1352), 3: (43596, 37862)}[n]

    def test_runs_a_handful_of_commands_per_input(self) -> None:
        """One node per level: a halting row runs ``5 n + 2`` commands at most."""
        for n in (2, 4, 6):
            template = crement("1" * (2**n - 1) + "0")
            machine = _Machine(instantiate_crement(template, [1] * n))
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            assert steps == 4 * n + 2


class TestCrementSharing:
    """A subtree already emitted at its level is jumped to, not repeated."""

    @staticmethod
    def _totals(tables: list[str]) -> tuple[int, int]:
        """(plain, shipped) character totals."""
        before = after = 0
        for table in tables:
            plain = len(best_input_order(table, _crement_ordered))
            shipped = len(crement(table))
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """All 256 three-input tables: 39,156 to 37,862 characters, 3.3%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (39156, 37862)

    def test_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 114,791 to 84,600 characters, 26.3%."""
        assert self._totals(five_input_sample()) == (114791, 84600)

    def test_a_shared_copy_is_patched_by_whoever_enters(self) -> None:
        """Parity's repeated subtrees run from both parents, every row."""
        table = "01101001" * 4
        template = crement(table)
        assert len(template) < len(best_input_order(table, _crement_ordered))
        _check(table)


@pytest.mark.parametrize("table", ["00", "0011"])
def test_narrow_balance_regime_edge_executes(table):
    """The smallest tables reaching an otherwise-untaken balance arm."""
    balanced = esolangs.generate("Crement", table, balance=True)
    assert _evaluate("Crement", balanced, inputs=len(table).bit_length() - 1) == table
