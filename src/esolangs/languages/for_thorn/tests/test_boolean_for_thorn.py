"""for_thorn generator tests."""

import random

import pytest

from esolangs import compat
from esolangs.generation.helpers import essential_inputs, permute_truth_table
from esolangs.languages import generators as boolean
from tests.generators.sample_tables import five_input_sample
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    verify_generated,
)


def _forth_scope_keys(table: str) -> set[int]:
    """The heap indices a Forþ program's definitions actually reach."""
    from esolangs.languages.for_thorn.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    machine = _Machine(boolean.for_thorn(table).split(",")[0], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    return set(machine.table)


def _forth_plain(table: str) -> str:
    """Forþ's build with no subtree shared: the fold alone, in natural order."""
    from esolangs.languages.for_thorn.generator import _forth_ordered

    n = len(table).bit_length() - 1
    natural = tuple(reversed(range(n)))
    return _forth_ordered(permute_truth_table(table, natural), ",68*-" * n)


class TestForth:
    def test_leaf_results_are_the_byte(self) -> None:
        """Each leaf pushes 48 + its table entry."""
        program = boolean.for_thorn("0001")
        assert "3F*3+" in program  # '0' leaves push 48 = 3*15+3
        assert "v68*+" in program
        assert "v77*v-" in boolean.for_thorn("1110")
        assert verify_generated("Forþ", "0001")
        assert verify_generated("Forþ", "1110")

    def test_scales(self) -> None:
        """More inputs mean more tree functions, and every input is read."""
        # Parity folds nothing under any order, so it spends the full tree.
        parity = "".join(str((row).bit_count() % 2) for row in range(32))
        assert _forth_plain(parity).count("{") == 2**5 - 2
        # Sharing keeps two dispatching nodes a level and two calls,
        # ending in two arithmetic bodies and two calls: 2 + 4 * 3.
        program = boolean.for_thorn(parity)
        assert program.count("{") == 14
        assert program.count(",68*-") == 5

    def test_constant_subtrees_fold(self) -> None:
        """A constant subtree answers in place and drops its descendants."""
        _check_constants()
        assert _forth_plain("1" * 8).count("{") == 2
        assert _forth_plain("01" * 4).count("{") == 2
        assert _forth_plain("0" * 4 + "1" * 4).count("{") == 6
        parity = "".join(str((row).bit_count() % 2) for row in range(8))
        assert _forth_plain(parity).count("{") == 2**3 - 2

    def test_folded_subtree_leaves_no_orphans(self) -> None:
        """Folding drops the whole subtree, not just the two children."""
        assert _forth_scope_keys("1" * 8) == set()
        # Nodes 2 and 4 fold; node 3 converts its last bit directly.
        assert _forth_scope_keys("00101010") == {1, 2, 3, 4}
        # An ignored input has no level: one node over the input that matters.
        assert _forth_scope_keys("0" * 4 + "1" * 4) == {1, 2}
        # AND folds node 1 and converts the last bit at node 2.
        assert _forth_scope_keys("0001") == {1, 2}

    def test_the_natural_stack_order_is_emitted(self) -> None:
        """Sharing never grows a table, and an ignored input is never a level."""
        for value in range(256):
            table = format(value, "08b")
            plain = _forth_plain(table)
            if len(essential_inputs(table, 3)) == 3:
                assert boolean.for_thorn(table) == min(
                    plain, boolean.for_thorn(table), key=len
                )
            else:  # an ignored input is read and dropped, never a level
                assert len(boolean.for_thorn(table)) <= len(plain)

    def test_sharing_totals(self) -> None:
        """Calling a repeated subtree's twin cuts the totals, growing none."""
        three = [format(value, "08b") for value in range(256)]
        for tables, before, after in (
            (three, 18688, 17344),
            (five_input_sample(), 62226, 55331),
        ):
            plain = [len(_forth_plain(table)) for table in tables]
            shared = [len(boolean.for_thorn(table)) for table in tables]
            assert (sum(plain), sum(shared)) == (before, after)
            assert all(s <= p for s, p in zip(shared, plain, strict=True))

    def test_subtree_ids_intern_each_level(self) -> None:
        """Equal subtables at a level share an id; constants are 0 and 1."""
        from esolangs.generation.helpers import subtree_ids

        assert subtree_ids("01101001") == [
            [6],
            [4, 5],
            [2, 3, 3, 2],
            [0, 1, 1, 0, 1, 0, 0, 1],
        ]
        assert subtree_ids("00001111") == [[2], [0, 1], [0, 0, 1, 1], [0] * 4 + [1] * 4]

    @pytest.mark.medium
    def test_sharing_executes_at_four_to_six(self) -> None:
        """A call lands on its twin's scope at every arity sampled."""

        rng = random.Random(0)
        for n in (4, 5, 6):
            for _ in range(8):
                table = format(rng.getrandbits(2**n), f"0{2**n}b")
                assert verify_generated("Forþ", table), table

    def test_const_large(self) -> None:
        """Constants above 225 need multiple base-15 digits."""
        from esolangs.languages.for_thorn.generator import _forth_const

        assert _forth_const(0) == "0"
        assert len(_forth_const(300)) > len(_forth_const(48))

    def test_const_is_base_fifteen(self) -> None:
        """Digits are ``0-E`` and the radix is 15, not 16."""
        from esolangs.languages.for_thorn.generator import _forth_const

        assert _forth_const(14) == "E"
        assert _forth_const(15) == "1F*0+"
        assert _forth_const(48) == "3F*3+"
        assert _forth_const(224) == "EF*E+"
        assert _forth_const(225) == "1F*0+F*0+"

    def test_the_program_is_only_forth_commands(self) -> None:
        """Only the characters Forþ reads are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.for_thorn(table)) <= set("*+,-.:123456789;ABCDEFcv{}"), (
                table
            )


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """``,0*+``."""
    assert_an_ignored_input_costs("Forþ", 6, 4)


def _check_constants() -> None:
    import esolangs
    from esolangs.languages.for_thorn.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = compat.generate("Forþ", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 2 * n + 4
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Forþ", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "7\n", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps < 2000
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_str() == "7"
                    if not options:
                        assert steps == 2 * n + 5
                    assert not machine.error
                    assert not machine.stack
                    assert not machine.table
                    if not options:
                        expected = (
                            8 * len(program)
                            + 10
                            - int(bit)
                            + 2 * (2 * n).bit_length()
                            + n.bit_length()
                        )
                        assert written.bits == expected
