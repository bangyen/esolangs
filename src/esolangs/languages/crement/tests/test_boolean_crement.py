"""Covers :mod:`esolangs.languages.crement.generator`."""

import random
from itertools import pairwise, product

import pytest

import esolangs
from esolangs.exceptions import TruthTableError
from esolangs.generation.helpers import TEMPLATE_CHAR, runs
from esolangs.languages.crement.generator import PAIR, _crement_ordered, crement
from esolangs.languages.crement.interpreter import _Machine
from esolangs.runtime._evaluate import _evaluate
from esolangs.vm import run_until_halt_or_cycle
from tests.generators.fills import fill
from tests.generators.sample_tables import five_input_sample
from tests.support.divergence import diverges
from tests.support.witness_tables import dense

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
        assert sizes == [34, 48, 128, 278, 416, 681, 1229, 2102, 3456, 6551]
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
        assert (old, new) == {2: (1416, 1330), 3: (42580, 37120)}[n]

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
            plain = len(
                _crement_ordered(table, tuple(range(len(table).bit_length() - 1)))
            )
            shipped = len(crement(table))
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """All 256 three-input tables: 43,596 to 37,862 characters, 13.2%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (42580, 37120)

    def test_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 127,301 to 84,600 characters, 33.5%."""
        assert self._totals(five_input_sample()) == (122316, 81574)

    def test_a_shared_copy_is_patched_by_whoever_enters(self) -> None:
        """Parity's repeated subtrees run from both parents, every row."""
        table = "01101001" * 4
        template = crement(table)
        assert len(template) < len(
            _crement_ordered(table, tuple(range(len(table).bit_length() - 1)))
        )
        _check(table)


@pytest.mark.parametrize("table", ["00", "0011"])
def test_narrow_balance_regime_edge_executes(table) -> None:
    """The smallest tables reaching an otherwise-untaken balance arm."""
    balanced = esolangs.generate("Crement", table, balance=True)
    assert _evaluate("Crement", balanced, inputs=len(table).bit_length() - 1) == table


def test_balanced_packed_template_instantiates_for_its_table() -> None:
    """A balanced, line-packed template still fills for its own table."""
    table = "0001011000111110"
    template = str(esolangs.generate("Crement", table, balance=True))
    for row, expected in enumerate(table):
        bits = [int(c) for c in format(row, "04b")]
        source = esolangs.instantiate("Crement", template, bits, truth_table=table)
        assert diverges("Crement", source, "") is (expected == "1")


# language-owners: ["ArrowQueue"]
# The shared verifier's timeout floor was measured across 123, ArrowQueue,
# Crement and Vandevelo on 0110, 0001, 10010110 and 00010111: 0.000s,
# every halting row sub-millisecond; its 1s bound has 1000x headroom.


def test_packed_rule_matches_the_k_scan() -> None:
    """Oracle: k0-1..k0+1 lines per row reach the best side of the full scan."""
    import random

    from esolangs.generation.wrap import balance_score
    from esolangs.languages.crement.generator import _packed, crement

    rng = random.Random(3)
    for n in range(1, 9):
        default = crement(format(rng.getrandbits(1 << n), f"0{1 << n}b"))
        lines = default.split("\n")
        scan = (
            "\n".join(" ".join(lines[i : i + k]) for i in range(0, len(lines), k))
            for k in range(2, len(lines))
        )
        best = min(map(balance_score, scan), default=(0,))[0]
        rule = min(map(balance_score, _packed(default)), default=(0,))[0]
        assert rule <= best


class TestCrementSweepPins:
    """Pins from the mutation sweep: the exact-width shortcut, the
    sub-six tester respelling and the balance packing count."""

    def test_a_template_exactly_as_wide_as_the_request_is_not_narrowed(self) -> None:
        program = crement(
            "00101100001000010100111101100100101100011000101010101100110101111000000011001011101100001110010111011000010011100111000111111101110111101000001111100110110100001110100100111101110100110100000010001111001011100001100010100101110000110101110010101101101011001000010100101000000000000110101110010101111100110001110000100011111010001110101000101011111000001010000011111111011101011010001011110100111110000110100101000101110001100000001111001001010101101101100001110001001010100100101100110011010101010110000101011101001100110110100111101001110100110010100001100011100100001111011111011100111001111000011000011101011111110011010001110100011111100000010010101110100101000101000101011111111001101101011101001000000001111111010011111111100000011100001010111100100100111111000111101111011111011010011001001100000000100111001000101001010110100100001001011010110110000000111010000101001000100001110011000110011101001011101010100100101000001001111000000100100100011110000111101010000101110010011100110100000100010111000011111111111110110011000001010000111101001001000111100111010001111101010101100101100001011010101000110010001001110110101001010111101000001001010110011110110111111001011000111001101110001101101001101010011010110100001101011000101100010000111001011011100100101001101011100001010000101110101110000000110011100010010010111110111100101001111110011000100110000010110111001101001100000100110111010110100111101000110110010100011001100001100101100001101111110011001001000001011111110111100101101101101110101001010110001111101001101110000100011010101111111001111000011011010001001011100000111100010011101000100001110000101111111010011100111101001001010100101010110111110101100111010000000011111000010011110000001100011101100100011010011011101010111111000100101100111100001100011011000000010111011010010011111110010001100100101101111101101100000111110110001111011010110001101110111011001010100000011111011101110000010111100100011100010010000100011101110111011000001100001001000000101000100010110101001001001101111100110000110011111101101111101111110101",
            width=10,
        )
        assert (
            len(program),
            program.count("\n") + 1,
            max(map(len, program.split("\n"))),
        ) == (11758, 1294, 10)

    def test_width_six_keeps_the_full_tester_placeholder(self) -> None:
        program = crement("0110", width=6)
        assert (
            len(program),
            program.count("\n") + 1,
            max(map(len, program.split("\n"))),
        ) == (113, 18, 6)

    def test_balanced_shape_is_pinned(self) -> None:
        program = str(
            esolangs.generate(
                "Crement",
                "00110000000011001001110100010000100110101010000001010110001111101001100110011110110101110001100000010010000001011100101111111101110011100010100111011100000001011101100110110011011101101010000100100011111100001011001111010011100110000101101111010100000110110110110001000100100111100010010101101001000010010101110001011101001100111011101011110000100001000001101011101001110011100001101010101110101010101100011101010111010010110110010010010011010010100011011001000100100010110011101110000110011111010111100001010011",
                balance=True,
            )
        )
        assert (
            len(program),
            program.count("\n") + 1,
            max(map(len, program.split("\n"))),
        ) == (3602, 46, 83)
