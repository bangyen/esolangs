"""forth generator tests."""

import importlib
import random

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import essential_inputs, permute_truth_table
from tests.generator_support import verify_generated
from tests.tools.boolean_runners import (
    run_forth,
)
from tests.tools.sample_tables import five_input_sample


def _forth_scope_keys(table: str) -> set[int]:
    """The heap indices a Forþ program's definitions actually reach."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.forth import _Machine

    machine = _Machine(boolean.forth(table).split(",")[0], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    return set(machine.table)


def _forth_plain(table: str) -> str:
    """Forþ's build with no subtree shared: the fold alone, in natural order."""
    from esolangs.tools.forth import _forth_ordered

    natural = tuple(reversed(range(len(table).bit_length() - 1)))
    return _forth_ordered(permute_truth_table(table, natural), natural)


class TestForth:
    def test_wide_table_skips_the_exponential_order_contest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Beyond n=10, use the natural order without enumerating 3**n orders."""
        module = importlib.import_module("esolangs.tools.forth")

        monkeypatch.setattr(
            module,
            "_forth_stack_programs",
            lambda _n: (_ for _ in ()).throw(AssertionError("order contest ran")),
        )
        program = module.forth("0" * (2**11))
        assert run_forth(program, ["0"] * 11) == "0"

    def test_leaf_results_are_the_byte(self) -> None:
        """Each leaf pushes 48 + its table entry."""
        program = boolean.forth("0001")
        assert "3F*3+" in program  # '0' leaves push 48 = 3*15+3
        assert "3F*4+" in program  # the '1' leaf pushes 49 = 3*15+4

    def test_scales(self) -> None:
        """More inputs mean more tree functions, and every input is read."""
        # Parity folds nothing under any order, so it spends the full tree.
        parity = "".join(str(bin(row).count("1") % 2) for row in range(32))
        assert _forth_plain(parity).count("{") == 2 ** (5 + 1) - 2
        # Sharing keeps two dispatching nodes a level (parity and its
        # complement) and two calls to them: 2 + 4 * 3 + 4 leaves.
        program = boolean.forth(parity)
        assert program.count("{") == 18
        assert program.count(",68*-") == 5

    def test_constant_subtrees_fold(self) -> None:
        """A constant subtree answers in place and drops its descendants."""
        assert _forth_plain("1" * 8).count("{") == 2
        assert _forth_plain("01" * 4).count("{") == 2
        assert _forth_plain("0" * 4 + "1" * 4).count("{") == 14
        parity = "".join(str(bin(row).count("1") % 2) for row in range(8))
        assert _forth_plain(parity).count("{") == 2 ** (3 + 1) - 2

    def test_folded_subtree_leaves_no_orphans(self) -> None:
        """Folding drops the whole subtree, not just the two children."""
        assert _forth_scope_keys("1" * 8) == {1, 2}
        # Nodes 2 and 4 are constant, so each drops its subtree: only 3's
        # leaves remain.
        assert _forth_scope_keys("00101010") == {1, 2, 3, 4, 7, 8}
        # An ignored input has no level: one node over the input that matters.
        assert _forth_scope_keys("0" * 4 + "1" * 4) == {1, 2}
        # The one-side fold keeps its sibling's descendants: AND's zero
        # subtree collapses to node 1 while 2 keeps 5 and 6.
        assert _forth_scope_keys("0001") == {1, 2, 5, 6}

    def test_the_natural_stack_order_is_emitted(self) -> None:
        """Forþ no longer contests reachable input orders."""
        from esolangs.tools.forth import _forth_ordered

        natural = (2, 1, 0)
        for value in range(256):
            table = format(value, "08b")
            builds = [
                _forth_ordered(permute_truth_table(table, natural), natural, share=s)
                for s in (False, True)
            ]
            if len(essential_inputs(table, 3)) == 3:
                assert boolean.forth(table) == min(builds, key=len)
            else:  # an ignored input is read and dropped, never a level
                assert len(boolean.forth(table)) <= len(min(builds, key=len))

    def test_rotations_are_interleaved_with_the_reads(self) -> None:
        """Weaving the rotations into the reads reaches more arrangements."""
        from esolangs.tools.forth import _forth_stack_programs

        # The reachable *set* has a closed form, which is what pins the
        # search: after each read the new bit is on top, and the only
        # lasting freedom is how far it sinks -- 0, 1 or 2 places, one
        # independent choice per read past the first.
        for n in range(2, 7):
            assert len(_forth_stack_programs(n)) == 2 * 3 ** (n - 2)
        assert len(_forth_stack_programs(3)) == 6  # all of 3!
        assert len(_forth_stack_programs(4)) == 18  # of 24
        assert len(_forth_stack_programs(5)) == 54  # of 120

        # The reads themselves are still one per input, whatever the weave.
        for n in (3, 4, 5):
            for program in _forth_stack_programs(n).values():
                assert program.count(",68*-") == n

    def test_sinking_a_bit_deeper_than_the_stack_is_skipped(self) -> None:
        """A sink needs values below it, so early reads have fewer choices."""
        from esolangs.tools.forth import _forth_stack_programs, _sink_top

        assert len(_forth_stack_programs(1)) == 1  # nothing to rearrange
        assert len(_forth_stack_programs(2)) == 2  # the second bit may swap

        # The sink itself keeps everything but the moved bit in order.
        assert _sink_top((0, 1, 2), 0) == (0, 1, 2)
        assert _sink_top((0, 1, 2), 1) == (0, 2, 1)
        assert _sink_top((0, 1, 2), 2) == (2, 0, 1)

    def test_an_unreachable_order_returns_empty_rather_than_building(self) -> None:
        """An order the ops cannot stack is declined, not approximated."""
        from esolangs.tools.forth import (
            _forth_ordered,
            _forth_stack_programs,
        )

        table = "0110100110010110"
        reachable = _forth_stack_programs(4)

        unreachable = (0, 1, 2, 3)
        assert tuple(reversed(unreachable)) not in reachable
        assert _forth_ordered(table, unreachable) == ""

        # The same table on an order the reads *can* stack still builds, so
        # the empty answer above is the order's doing and not the table's.
        buildable = (0, 1, 3, 2)
        assert tuple(reversed(buildable)) in reachable
        assert _forth_ordered(table, buildable) != ""

    def test_sharing_totals(self) -> None:
        """Calling a repeated subtree's twin cuts the totals, growing none."""
        three = [format(value, "08b") for value in range(256)]
        for tables, before, after in (
            (three, 28672, 24418),
            (five_input_sample(), 93764, 63240),
        ):
            plain = [len(_forth_plain(table)) for table in tables]
            shared = [len(boolean.forth(table)) for table in tables]
            assert (sum(plain), sum(shared)) == (before, after)
            assert all(s <= p for s, p in zip(shared, plain, strict=True))

    def test_subtree_ids_intern_each_level(self) -> None:
        """Equal subtables at a level share an id; constants are 0 and 1."""
        from esolangs.tools.helpers import subtree_ids

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
        from esolangs.tools.forth import _forth_const

        assert _forth_const(0) == "0"
        assert len(_forth_const(300)) > len(_forth_const(48))

    def test_const_is_base_fifteen(self) -> None:
        """Digits are ``0-E`` and the radix is 15, not 16."""
        from esolangs.tools.forth import _forth_const

        assert _forth_const(14) == "E"
        assert _forth_const(15) == "1F*0+"
        assert _forth_const(48) == "3F*3+"
        assert _forth_const(224) == "EF*E+"
        assert _forth_const(225) == "1F*0+F*0+"

    def test_the_program_is_only_forth_commands(self) -> None:
        """Only the characters Forþ reads are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.forth(table)) <= set("*+,-.:123456789;ABCDEFcv{}"), table
