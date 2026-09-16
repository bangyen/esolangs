"""Covers :mod:`esolangs.tools.crement`."""

import random
from itertools import pairwise, product

import pytest

from esolangs.exceptions import TruthTableError
from esolangs.interpreters.other.crement import _Machine
from esolangs.tools.crement import crement, instantiate_crement
from esolangs.vm import run_until_halt_or_cycle


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
        assert [line for line in template.splitlines() if "{" in line] == [
            "{X0}",
            "{X1}",
            "{X2}",
        ]
        assert "{C" not in template

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
        """A one-dependency table is one node; parity is a full tree."""
        assert len(crement("11110000")) < len(crement("10010110"))
        assert crement("11110000").splitlines()[9:] == ["+A 3 0", "+A 4 1", "+J 3 1"]
        assert crement("10010110").count("\n") + 1 == 3 + 6 + 3 * 7

    def test_sizes_double_per_added_input(self) -> None:
        """Dense templates through n=8 grow about twofold per added input.

        Each node is three lines whose operands are a tester's line number
        or an offset into the node's own subtree, so the size tracks the
        node count and the ratio settles at two once the tree dominates
        the fixed header.
        """
        sizes = [len(crement(_dense(n))) for n in range(1, 9)]
        assert sizes == [53, 89, 193, 375, 777, 1524, 3057, 6087]
        ratios = [b / a for a, b in pairwise(sizes)]
        assert all(1.6 <= r <= 2.2 for r in ratios), ratios
        assert all(1.95 <= r <= 2.05 for r in ratios[-3:]), ratios

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
