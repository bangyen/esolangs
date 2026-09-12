"""Unit tests for the stack-based boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.stack`: Grapheme,
Forþ, Modulous, BFStack, and Unsquare.
"""

import pytest

import esolangs
from esolangs.tools import boolean
from esolangs.tools.boolean import stack
from esolangs.tools.boolean.helpers import permute_truth_table
from tests.tools.boolean_runners import (
    run_bfstack,
    run_forth,
    run_grapheme,
    run_modulous,
)


def _grapheme_counted_side(table: str, n: int) -> str:
    """The build the retired row-count rule would have chosen.

    It took the zero side when ``len(zeros) <= len(ones)``, so ties went to
    that side.  Kept here rather than in the generator: it is the thing the
    generator is asserted to beat, not something it should be able to emit.
    """
    from esolangs.tools.boolean.stack import _grapheme_head, _grapheme_side

    head, reduced, width = _grapheme_head(table, n)
    zeros = reduced.count("0")
    return _grapheme_side(reduced, width, head, zero_rows=zeros <= reduced.count("1"))


class TestGrapheme:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.grapheme(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_grapheme(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.grapheme(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_grapheme(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_shorter_side_wins_not_the_sparser_one(self) -> None:
        """Row count is a proxy for length, and it picks wrong.

        A row's cost falls with its popcount -- a negated literal spends
        eight characters more than a plain one -- and the two sides seed the
        accumulator differently (7 characters against 3), so equal counts do
        not mean equal length.  The old rule compared counts and gave ties
        to the expensive seed, so a balanced table always lost.

        Both sides are built now and the shorter kept.  ``00010111`` is the
        worst case at n == 3, and the count rule cost it 52 characters.
        """
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            shipped = len(boolean.grapheme(table))
            # What the count rule would have picked, built directly.
            counted = len(_grapheme_counted_side(table, 3))
            assert shipped <= counted, table
            improved += shipped < counted
        assert improved == 45

    def test_balanced_table_takes_the_cheaper_seed(self) -> None:
        """The old ``<=`` tie went to the 7-character seed every time."""
        program = boolean.grapheme("0011")
        assert len(program) < len(_grapheme_counted_side("0011", 2))
        for combo in range(4):
            bits = [(combo >> (1 - i)) & 1 for i in range(2)]
            got = run_grapheme(program, [str(b) for b in bits])
            assert got == "0011"[combo], f"inputs {bits}"

    def test_the_program_is_only_grapheme_commands(self) -> None:
        """Only the letters Grapheme reads as commands are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.grapheme(table)) <= set("ABCDEFGIRSTWYZ"), table


class TestForth:
    def test_program_structure(self) -> None:
        """The program defines one function per surviving node, reading n bits.

        AND's zero-side subtree is constant, so it folds to a leaf: four
        nodes rather than the full six.
        """
        program = boolean.forth("0001")
        assert program.endswith("1+;.")
        assert program.count("{") == program.count("}") == 4
        assert program.count(",68*-") == 2  # read and normalize 2 inputs

    def test_leaf_results_are_the_byte(self) -> None:
        """Each leaf pushes 48 + its table entry."""
        program = boolean.forth("0001")
        assert "3F*3+" in program  # '0' leaves push 48 = 3*15+3
        assert "3F*4+" in program  # the '1' leaf pushes 49 = 3*15+4

    def test_scales(self) -> None:
        """More inputs mean more tree functions, and every input is read."""
        # Parity folds nothing under any order, so it spends the full tree.
        parity = "".join(str(bin(row).count("1") % 2) for row in range(32))
        program = boolean.forth(parity)
        assert program.count("{") == 2 ** (5 + 1) - 2
        assert program.count(",68*-") == 5

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_truth_table(self, n: int) -> None:
        """Every table up to three inputs produces the right result.

        The other Forþ tests assert program structure only; this runs the
        program, which is what pins the fold's behaviour rather than its
        shape.
        """
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.forth(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_forth(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        """A constant subtree answers in place and drops its descendants.

        Forþ stores each scope in a dict keyed by the number pushed before
        ``{`` and calls it with a default, so an unemitted node simply
        never exists -- folding is skip-emission with no renumbering.

        Which subtrees are constant depends on the order the tree splits
        in, and the order is chosen per table: ``00001111`` depends on the
        first input alone and ``01010101`` on the last, so each collapses to
        the two root children under the order that tests its input first.
        A stack-ordered tree could only fold the second.

        Parity is what folds under no order at all, so it is the witness
        that the fold is doing work rather than the search hiding it.
        """
        assert boolean.forth("1" * 8).count("{") == 2
        assert boolean.forth("01" * 4).count("{") == 2
        assert boolean.forth("0" * 4 + "1" * 4).count("{") == 2
        parity = "".join(str(bin(row).count("1") % 2) for row in range(8))
        assert boolean.forth(parity).count("{") == 2 ** (3 + 1) - 2

    def test_folded_subtree_leaves_no_orphans(self) -> None:
        """Folding drops the whole subtree, not just the two children.

        A grandchild below a folded node is just as unreachable; emitting
        it would be dead code the program never calls, so the node count
        must fall to exactly the surviving frontier.
        """
        from esolangs.tools.boolean.stack import _forth_const

        program = boolean.forth("1" * 8)
        for m in range(3, 15):  # every node below the two root children
            assert _forth_const(m) + "{" not in program

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than the stack-ordered program.

        The natural order here is the *reversal* -- ``;`` pops, so the tree
        has always tested the last input at the root -- and it is tried
        first with ties keeping it.  Pinning against that build is what
        proves the search cannot churn an emission it does not shorten.
        """
        from esolangs.tools.boolean.stack import _forth_ordered

        natural = (2, 1, 0)
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.forth(table))
            stack_ordered = len(
                _forth_ordered(permute_truth_table(table, natural), natural)
            )
            assert dispatched <= stack_ordered, table
            improved += dispatched < stack_ordered
        assert improved == 112

    def test_rotations_are_interleaved_with_the_reads(self) -> None:
        """Weaving the rotations into the reads reaches more arrangements.

        ``v`` and ``c`` touch only the top three cells, so rotating after
        all ``n`` reads can only permute the last three bits -- 6
        arrangements however wide the table.  Moving a bit while it is
        still near the top reaches three times as many at n == 4 and nine
        times as many at n == 5, which is what keeps the saving from
        collapsing as ``n`` grows.
        """
        from esolangs.tools.boolean.stack import _forth_stack_programs

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
        """A sink needs values below it, so early reads have fewer choices.

        The first read cannot sink at all and the second can sink at most
        one place, which is why the arrangement count is ``2 * 3**(n - 2)``
        rather than ``3**n``: the enumeration walks every combination and
        drops the ones that would sink a bit past the bottom of the stack.
        """
        from esolangs.tools.boolean.stack import _forth_stack_programs, _sink_top

        assert len(_forth_stack_programs(1)) == 1  # nothing to rearrange
        assert len(_forth_stack_programs(2)) == 2  # the second bit may swap

        # The sink itself keeps everything but the moved bit in order.
        assert _sink_top((0, 1, 2), 0) == (0, 1, 2)
        assert _sink_top((0, 1, 2), 1) == (0, 2, 1)
        assert _sink_top((0, 1, 2), 2) == (2, 0, 1)

    def test_an_unreachable_order_returns_empty_rather_than_building(self) -> None:
        """An order the ops cannot stack is declined, not approximated.

        Only 18 of the 24 orders are reachable at n == 4, so ``forth`` has
        to be able to ask for one and be told no -- the empty string is the
        signal to try a different order.  Building something for an order
        the reads cannot produce would emit a program that tests its inputs
        in the wrong places, which is why this returns rather than falling
        through to the tree.
        """
        from esolangs.tools.boolean.stack import (
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

    def test_const_large(self) -> None:
        """Constants above 225 need multiple base-15 digits."""
        from esolangs.tools.boolean.stack import _forth_const

        assert _forth_const(0) == "0"
        assert len(_forth_const(300)) > len(_forth_const(48))

    def test_const_is_base_fifteen(self) -> None:
        """Digits are ``0-E`` and the radix is 15, not 16.

        Forþ spells a literal digit by digit, so the radix decides both the
        digits used and how many there are.  A radix one too large still
        builds *a* number for every constant the generator needs -- the
        digits stay inside the alphabet and the arithmetic still lands --
        so only the spelling shows it.  These are the boundaries: 14 is the
        last single digit, 15 rolls over, and 225 is the first three-digit
        constant.
        """
        from esolangs.tools.boolean.stack import _forth_const

        assert _forth_const(14) == "E"
        assert _forth_const(15) == "1F*0+"
        assert _forth_const(48) == "3F*3+"
        assert _forth_const(224) == "EF*E+"
        assert _forth_const(225) == "1F*0+F*0+"

    def test_length_formula_matches_the_built_program(self) -> None:
        """The closed-form score equals the built length for every order.

        ``forth`` picks its input order by ``_forth_order_length`` and
        builds only the winner, so a drift between formula and builder
        ships a wrong winner that still runs.  n == 3 is exhaustive over
        tables and orders; n == 7 is the first arity where a level's heap
        indices cross a base-15 digit boundary, so the per-node savings
        fallback fires rather than the shared-scalar path.
        """
        import random

        from esolangs.tools.boolean.helpers import permute_truth_table
        from esolangs.tools.boolean.stack import (
            _forth_order_length,
            _forth_ordered,
            _forth_permuted_bits,
            _forth_stack_programs,
        )

        rng = random.Random(7)
        tables = [format(v, "08b") for v in range(256)]
        tables += ["".join(rng.choice("01") for _ in range(128)) for _ in range(2)]
        for table in tables:
            n = len(table).bit_length() - 1
            bits = int(table[::-1], 2)
            for arrangement, reads in _forth_stack_programs(n).items():
                perm = tuple(reversed(arrangement))
                got = _forth_order_length(
                    _forth_permuted_bits(bits, perm, n), n, len(reads)
                )
                want = len(_forth_ordered(permute_truth_table(table, perm), perm))
                assert got == want, (table, perm)

    def test_the_program_is_only_forth_commands(self) -> None:
        """Only the characters Forþ reads are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.forth(table)) <= set("*+,-.123456789;ABCDEFcv{}"), table


class TestModulous:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.modulous(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_modulous(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input then branches on it."""
        assert boolean.modulous("10").startswith("[INP INT]")
        assert "[JMP F 2 IF 0]" in boolean.modulous("10")

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice pushes its answer instead of branching further.

        Modulous branches on the stack top, which is the *last* input, so
        its subtrees are strided rather than contiguous runs -- a table
        like ``11110000`` has no constant subtree under that split and
        folds nothing.  A table that agrees outright still collapses to a
        single push, which is where the saving comes from.
        """
        leaves = "[PRT INT]"
        assert boolean.modulous("11111111").count(leaves) == 1
        assert boolean.modulous("10010110").count(leaves) == 8


class TestBfstack:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bfstack(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bfstack(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_encode_decode_structure(self) -> None:
        """The program encodes the inputs then tests the zero rows."""
        program = boolean.bfstack("0110")
        assert program.startswith(">>+,")  # result cell, accumulator, first input
        assert program.count(",") == 2  # one read per input
        assert program.endswith("+" * 48 + ".")  # print 48 + result

    def test_the_program_is_only_bfstack_commands(self) -> None:
        """No character outside the eight commands is emitted.

        BFStack ignores anything it does not recognise, the brainfuck
        convention, so a stray character is a *no-op* rather than an error:
        splicing one beside a ``[`` leaves the program computing exactly
        the same table.  That makes every behavioural check blind to it,
        and the alphabet the only thing that is not.
        """
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.bfstack(table)) <= set("+,-.<>[]"), table


class TestUnsquare:
    def test_program_shape(self) -> None:
        """The program reads n inputs and prints once.

        The reads are no longer necessarily consecutive: a sink that
        reorders the tree is emitted *between* them, because a bit has to
        be moved while it is still near the top.  What stays invariant is
        that there is one read per input and the program still consumes its
        input stream in order.
        """
        program = boolean.unsquare("0110")
        assert program.startswith("iA>-<P")
        assert program.count("iA>-<P") == 2  # one read per input
        assert program.endswith("o")

        # A table whose best order needs a sink still reads once per input.
        for value in range(256):
            assert boolean.unsquare(format(value, "08b")).count("iA>-<P") == 3

    def test_past_the_cap_only_the_natural_order_is_built(self) -> None:
        """Above ``_ORDER_SEARCH_MAX`` the arrangement search is skipped.

        The reachable arrangements are ``2 * 3**(n - 2)`` rather than
        ``n!``, but that is still a program built per candidate, so the
        shared cap applies.  Past it the generator emits the natural order
        alone -- what it produced before reordering existed, never worse,
        just unimproved -- and this pins that only one program is built.
        """
        from esolangs.tools.boolean.helpers import _ORDER_SEARCH_MAX

        n = _ORDER_SEARCH_MAX + 1
        table = "01" * (2 ** (n - 1))
        program = boolean.unsquare(table)

        assert program.count("iA>-<P") == n  # one read per input
        assert program.endswith("o")

    def test_reordering_never_grows_a_program(self) -> None:
        """Choosing the stack arrangement can only shrink the program.

        The natural order here is the *reversal* -- ``A`` pops, so the tree
        has always tested the last input at the root -- and it is tried
        first with ties keeping it, so a table no reorder helps emits
        exactly what it emitted before.
        """
        from esolangs.tools.boolean.stack import (
            _unsquare_stack_programs,
            _unsquare_tree,
        )

        n = 3
        natural = tuple(reversed(range(n)))
        prefix = _unsquare_stack_programs(n)[tuple(reversed(natural))]
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            reordered = len(boolean.unsquare(table))
            stack_ordered = len(
                prefix
                + _unsquare_tree(
                    permute_truth_table(table, tuple(reversed(natural))), n
                )
            )
            assert reordered <= stack_ordered, table
            improved += reordered < stack_ordered
        assert improved == 112

    def test_reorder_cost_selects_the_emitted_program(self) -> None:
        """The pricing model matches every candidate and picks the shortest."""
        from esolangs.tools.boolean.stack import (
            _unsquare_cost,
            _unsquare_stack_programs,
            _unsquare_tree,
        )

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                costs = []
                for arrangement, prefix in _unsquare_stack_programs(n).items():
                    permuted = permute_truth_table(table, arrangement)
                    assert _unsquare_cost(permuted, n, prefix) == len(
                        prefix + _unsquare_tree(permuted, n)
                    )
                    costs.append(_unsquare_cost(permuted, n, prefix))
                assert len(boolean.unsquare(table)) == min(costs)

    def test_sinks_are_interleaved_with_the_reads(self) -> None:
        """Weaving the sinks into the reads is what reaches the arrangements.

        A bit stashed in the accumulator does not survive a read block --
        the block's own ``A`` overwrites it -- so a bit has to be sunk while
        it is still near the top, before later reads bury it.

        The reachable *set* has a closed form, which is why no search is
        needed: after each read the new bit is on top and the only lasting
        freedom is how far it sinks (0, 1 or 2 places), one independent
        choice per read past the first.  Forþ's stack has the same count for
        the same reason, reached through different ops.
        """
        from esolangs.tools.boolean.stack import _unsquare_stack_programs

        for n in range(2, 7):
            assert len(_unsquare_stack_programs(n)) == 2 * 3 ** (n - 2)
        assert len(_unsquare_stack_programs(3)) == 6  # all of 3!
        assert len(_unsquare_stack_programs(4)) == 18  # of 24
        assert len(_unsquare_stack_programs(5)) == 54  # of 120

        # The reads themselves are still one per input, whatever the weave.
        for n in (3, 4, 5):
            for program in _unsquare_stack_programs(n).values():
                assert program.count("iA>-<P") == n

    def test_two_place_sink_needs_the_leading_swap(self) -> None:
        """Sinking two places is ``SASP``; ``ASP`` alone does something else.

        ``A`` lifts the *top* out, so the ``S`` that follows swaps the pair
        beneath it and ``P`` returns the bit to where it started -- which
        reorders the wrong two cells.  The leading ``S`` is what moves the
        bit down first so the pair it must cross ends up above it.  This is
        pinned because the difference is invisible in the arrangement count
        (both spellings reach the same number of arrangements) and shows up
        only as a program computing the wrong function.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.unsquare import _Machine

        def apply(ops: str) -> tuple[int, ...]:
            machine = _Machine(ops, ScriptedIO(""))
            machine.load((10, 20, 30))
            for _ in range(100):
                if machine.halted:
                    break
                machine.step()
            return machine.stack

        assert apply("SASP") == (30, 10, 20)  # the top sank two places
        assert apply("ASP") == (20, 10, 30)  # the top never moved

    def test_decision_tree(self) -> None:
        """Each internal node branches on a bit with the flip primitive."""
        program = boolean.unsquare("0110")
        assert "x->IA<" in program  # the stack-clean flip
        assert program.count("x>") >= 3  # one guard per branch

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints its answer instead of branching further.

        Like Modulous, Unsquare branches on the last input first, so its
        subtrees are strided and a table such as ``11110000`` folds
        nothing; a table that agrees outright collapses to one leaf.
        """
        assert boolean.unsquare("11111111").count("P") == 3 + 1  # 3 reads, 1 leaf
        assert boolean.unsquare("10010110").count("P") == 3 + 8

    def test_the_program_is_only_unsquare_commands(self) -> None:
        """Only the characters Unsquare reads are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.unsquare(table)) <= set("+-<>AIOPSiox"), table


class TestGraphemeKeysAvoidItsOwnAlphabet:
    """Two variable keys collided with the language, and only one raised.

    Both were invisible to the arity sweep in
    ``tests/tools/test_boolean_contract.py``, which builds every generator
    to ten inputs but never runs what it builds.  ``boolean.grapheme``
    returned a healthy-looking program for all of these.
    """

    @staticmethod
    def _one_minterm(n: int) -> str:
        """A table whose single 1 makes every one of its ``n`` inputs matter."""
        return "1" + "0" * (2**n - 1)

    def test_no_key_letter_is_the_int_mode_delimiter(self) -> None:
        """``F`` framed the key, so it could not also be the digit inside it."""
        assert "F" not in stack._GRAPHEME_KEY_LETTERS  # noqa: SLF001

    def test_no_key_letter_aliases_the_constant(self) -> None:
        """The normalizing 65 owns key 90, and a slot must not store over it."""
        keys = [
            stack._grapheme_slot_key(slot)  # noqa: SLF001
            for slot in range(len(stack._GRAPHEME_KEY_LETTERS))  # noqa: SLF001
        ]
        assert stack._GRAPHEME_CONST_KEY not in keys  # noqa: SLF001
        assert len(set(keys)) == len(keys)

    @pytest.mark.parametrize("n", [6, 7, 8, 9])
    def test_a_table_using_every_input_still_computes(self, n: int) -> None:
        """Six essential inputs reached slot 5, and slot 5's key was ``FFF``.

        Under the old alphabet six raised ``ProgramError: Grapheme produced
        no answer this could read`` and seven raised ``HaltError: G needs a
        string or a function``.  Five and below were always fine, at any
        arity, because the wall stood at essential inputs rather than table
        size -- a dense n=9 table that folds to one input never saw it.
        """
        table = self._one_minterm(n)
        assert esolangs.evaluate("Grapheme", table, timeout=60) == table

    def test_parity_at_six_inputs_computes(self) -> None:
        """Parity is the table with nothing to fold, so all six slots are live."""
        table = "".join(str(bin(row).count("1") & 1) for row in range(64))
        assert esolangs.evaluate("Grapheme", table, timeout=60) == table

    def test_the_constant_alias_returned_a_wrong_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The positive control, and the reason ``I`` is filtered out.

        Dropping only ``F`` leaves ``I`` at slot 7 holding key 90 -- the
        constant's.  That collision does not raise: eight essential inputs
        still come out right, because slot 7 is read last and nothing reads
        the constant after it.  Nine is where the clobbered 65 is read back
        and the table comes out wrong, quietly.  Without this control the
        ``I`` skip looks like superstition.
        """
        monkeypatch.setattr(
            stack,
            "_GRAPHEME_KEY_LETTERS",
            [letter for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if letter != "F"],
        )
        table = self._one_minterm(9)
        assert esolangs.evaluate("Grapheme", table, timeout=60) != table
