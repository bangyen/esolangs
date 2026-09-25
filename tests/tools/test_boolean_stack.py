"""Unit tests for the stack-based boolean generators.

Covers the generators in :mod:`esolangs.tools.stack`: Grapheme,
Forþ, Modulous, BFStack, and Unsquare.
"""

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.tools import stack
from esolangs.tools.helpers import permute_truth_table
from tests.tools.boolean_runners import (
    run_bfstack,
    run_forth,
    run_grapheme,
    run_modulous,
    run_unsquare,
)


def _forth_scope_keys(table: str) -> set[int]:
    """The heap indices a Forþ program's definitions actually reach.

    Runs the definition prefix -- everything before the first read, and
    ``,`` is the only read -- and returns the interpreter's scope table.
    The generator labels each definition with the step from the previous
    one, so the index a node lands on is a running sum that only the
    interpreter resolves.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.forth import _Machine

    machine = _Machine(boolean.forth(table).split(",")[0], ScriptedIO(""))
    while not machine.halted:
        machine.step()
    return set(machine.table)


class TestGrapheme:
    def test_a_literal_pushes_ten_times_any_value(self) -> None:
        """Int mode spells every value, 6 included, as one literal."""
        from esolangs.tools.stack import _grapheme_literal

        for value in (0, 1, 16, 106, 1006, 1_263_460, 9_999_996, 5_666_666):
            code = _grapheme_literal(value)
            assert run_grapheme(code + "Y", []) == str(10 * value), value

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

    def test_there_is_no_branch_left(self) -> None:
        """Indexing a literal needs no skip: parity emits no ``U``/``V``/``X``."""
        parity = boolean.grapheme("01101001")
        assert set("UVX").isdisjoint(parity)
        assert set("UVX").isdisjoint(boolean.grapheme("0" * 8))

    def test_the_table_costs_about_a_third_of_a_character_an_entry(self) -> None:
        """The literal is the table in base 10, so log10(2) letters an entry."""
        sizes = []
        for n in (7, 11):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.grapheme(table)))
        grown = (sizes[1] - sizes[0]) / ((1 << 11) - (1 << 7))
        assert 0.30 < grown < 0.35, sizes

    def test_the_program_is_only_grapheme_commands(self) -> None:
        """Only int-mode digits and the eleven commands used are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.grapheme(table)) <= set("ABCDEFGHIKLPRSTWYZ"), table


class TestForth:
    def test_wide_table_skips_the_exponential_order_contest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Beyond n=10, use the natural order without enumerating 3**n orders."""
        import esolangs.tools.stack as stack

        monkeypatch.setattr(
            stack,
            "_forth_stack_programs",
            lambda _n: (_ for _ in ()).throw(AssertionError("order contest ran")),
        )
        program = stack.forth("0" * (2**11))
        assert run_forth(program, ["0"] * 11) == "0"

    def test_program_structure(self) -> None:
        """The program defines one function per surviving node, reading n bits.

        AND's zero-side subtree is constant, so it folds to a leaf: four
        nodes rather than the full six.
        """
        program = boolean.forth("0001")
        # The root dup is what hands the callee its own index, which is
        # what lets every node below spell its children as a step.
        assert program.endswith("1+:;.")
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

        The natural stack order tests the last input first, so
        ``01010101`` collapses to the two root children while ``00001111``
        does not.

        Parity is what folds under no order at all, so it is the witness
        that the fold is doing work rather than the search hiding it.
        """
        assert boolean.forth("1" * 8).count("{") == 2
        assert boolean.forth("01" * 4).count("{") == 2
        assert boolean.forth("0" * 4 + "1" * 4).count("{") == 14
        parity = "".join(str(bin(row).count("1") % 2) for row in range(8))
        assert boolean.forth(parity).count("{") == 2 ** (3 + 1) - 2

    def test_folded_subtree_leaves_no_orphans(self) -> None:
        """Folding drops the whole subtree, not just the two children.

        A grandchild below a folded node is just as unreachable; emitting
        it would be dead code the program never calls, so the node count
        must fall to exactly the surviving frontier.

        Asserted against the scope table the interpreter actually builds,
        not against the emitted text.  The labels are steps between
        indices rather than the indices themselves, so searching the source
        for one would pass whatever the generator emitted.
        """
        assert _forth_scope_keys("1" * 8) == {1, 2}
        assert _forth_scope_keys("0" * 4 + "1" * 4) == set(range(1, 15))
        # The one-side fold keeps its sibling's descendants: AND's zero
        # subtree collapses to node 1 while 2 keeps 5 and 6.
        assert _forth_scope_keys("0001") == {1, 2, 5, 6}

    def test_the_natural_stack_order_is_emitted(self) -> None:
        """Forþ no longer contests reachable input orders."""
        from esolangs.tools.stack import _forth_ordered

        natural = (2, 1, 0)
        for value in range(256):
            table = format(value, "08b")
            assert boolean.forth(table) == _forth_ordered(
                permute_truth_table(table, natural), natural
            )

    def test_rotations_are_interleaved_with_the_reads(self) -> None:
        """Weaving the rotations into the reads reaches more arrangements.

        ``v`` and ``c`` touch only the top three cells, so rotating after
        all ``n`` reads can only permute the last three bits -- 6
        arrangements however wide the table.  Moving a bit while it is
        still near the top reaches three times as many at n == 4 and nine
        times as many at n == 5, which is what keeps the saving from
        collapsing as ``n`` grows.
        """
        from esolangs.tools.stack import _forth_stack_programs

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
        from esolangs.tools.stack import _forth_stack_programs, _sink_top

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
        from esolangs.tools.stack import (
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
        from esolangs.tools.stack import _forth_const

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
        from esolangs.tools.stack import _forth_const

        assert _forth_const(14) == "E"
        assert _forth_const(15) == "1F*0+"
        assert _forth_const(48) == "3F*3+"
        assert _forth_const(224) == "EF*E+"
        assert _forth_const(225) == "1F*0+F*0+"

    def test_the_program_is_only_forth_commands(self) -> None:
        """Only the characters Forþ reads are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.forth(table)) <= set("*+,-.:123456789;ABCDEFcv{}"), table


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
        """The table is one literal and the program prints one of its bytes."""
        program = boolean.modulous("10010110")
        assert program.startswith('[PSH STR "10010110"]')
        assert program.count("[INP INT]") == 3
        assert program.endswith("[PRT][END]")

    def test_size_is_the_table_plus_a_fixed_frame(self) -> None:
        """No branch reads the table, so its contents cannot change the size.

        The old route was a decision tree, which meant a constant subtree
        collapsed and a table like parity did not -- 45 characters an entry
        against this one's frame plus a byte.  Length depending only on the
        arity is the signature of the lookup that replaced it.
        """
        sizes = {
            len(boolean.modulous(table))
            for table in ("11111111", "10010110", "00000000", "11110000")
        }
        assert len(sizes) == 1
        assert len(boolean.modulous("1" * 16)) - sizes.pop() == 16 - 8 + 49


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
    """The table lives on the stack; the reads pop down to the answer."""

    @staticmethod
    def _rows(table: str) -> list[str]:
        """Every row of ``table`` as the generated program answers it."""
        n = (len(table) - 1).bit_length()
        program = boolean.unsquare(table)
        return [
            run_unsquare(program, list(format(row, f"0{n}b"))) for row in range(2**n)
        ]

    def test_program_shape(self) -> None:
        """The table is pushed first, then one read an input, then the print."""
        program = boolean.unsquare("0110")
        assert program.startswith("OIIO")  # the table, reversed, one cell a row
        assert program.count("i") == 2  # one read an input
        assert program.endswith("o")

        for value in range(256):
            assert boolean.unsquare(format(value, "08b")).count("i") == 3

    def test_two_bytes_a_row(self) -> None:
        """Size is the table plus its addressing, not a tree over it.

        ``2**n`` cells and ``2**n - 1`` pops, so the constant is 2 either
        side of the reads; the old decision tree spent 32.5 a row.
        """
        for n in range(2, 11):
            table = "".join("01"[(row * row) % 3 % 2] for row in range(2**n))
            size = len(boolean.unsquare(table))
            assert size - 2 * 2**n == 10 * n + 26, n

    def test_every_row_of_every_small_table(self) -> None:
        """Exhaustive at n <= 3: 276 tables, every row executed."""
        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                assert "".join(self._rows(table)) == table, table

    def test_a_program_answers_its_own_table_only(self) -> None:
        """The positive control: XOR's program disagrees with XNOR everywhere."""
        assert "".join(self._rows("0110")) != "1001"

    def test_inessential_inputs_cost_a_read_not_a_table(self) -> None:
        """An ignored input is consumed by ``iA`` and never widens the table.

        The stream is still read in full -- a program that stopped early
        would leave the harness's remaining lines unread -- but the cells
        below count only the inputs that matter.
        """
        program = boolean.unsquare("01010101")  # depends on the last input alone
        assert program.count("i") == 3
        assert program.startswith("IOiA")  # two cells, then the first skip
        assert "".join(self._rows("01010101")) == "01010101"

    def test_the_program_is_only_unsquare_commands(self) -> None:
        """Only the characters Unsquare reads are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.unsquare(table)) <= set("+-<>AIOPiox"), table


class TestGraphemeTable:
    """The one literal holding the table, and the index that shifts it."""

    @staticmethod
    def _one_minterm(n: int) -> str:
        """A table whose single 1 makes every one of its ``n`` inputs matter."""
        return "1" + "0" * (2**n - 1)

    def test_padding_never_reaches_an_entry(self) -> None:
        """Every entry survives the lift that forces a leading decimal 1."""
        for n in range(1, 9):
            for table in (self._one_minterm(n), "01" * (2 ** (n - 1))):
                packed = stack._grapheme_table(table)  # noqa: SLF001
                assert str(packed)[0] == "1"
                low = format(packed % (1 << len(table)), f"0{len(table)}b")
                assert low == table

    @pytest.mark.parametrize("n", [6, 7, 8, 9])
    def test_a_table_using_every_input_still_computes(self, n: int) -> None:
        """Six essential inputs reached slot 5, whose old key was ``FFF``.

        Under the one-letter key alphabet six raised ``ProgramError: Grapheme
        produced no answer this could read`` and seven raised ``HaltError: G
        needs a string or a function``.  There are no slot keys left to
        collide, but the arities that broke stay pinned.
        """
        table = self._one_minterm(n)
        assert esolangs.evaluate("Grapheme", table, timeout=60) == table

    def test_parity_at_six_inputs_computes(self) -> None:
        """Parity is the table with nothing to fold, so every input is live."""
        table = "".join(str(bin(row).count("1") & 1) for row in range(64))
        assert esolangs.evaluate("Grapheme", table, timeout=60) == table

    def test_an_off_by_one_shift_returns_a_wrong_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The positive control: the index is load-bearing, not decoration.

        Doubling the packed table shifts every entry one bit up, which the
        accumulator's power of two no longer cancels.  Without this control a
        table that happened to read right anywhere would look like proof.
        """
        packed = stack._grapheme_table  # noqa: SLF001
        monkeypatch.setattr(stack, "_grapheme_table", lambda t: 2 * packed(t))
        table = self._one_minterm(6)
        assert esolangs.evaluate("Grapheme", table, timeout=60) != table
