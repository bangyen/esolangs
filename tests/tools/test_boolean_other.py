"""Unit tests for the single-language boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.other` and
:mod:`esolangs.tools.boolean.ztoalc_l`, plus the shared validation and
helper edge paths exercised across generator modules.
"""

import importlib
import itertools
import random

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools import boolean, laserfuck_layout
from tests.tools.boolean_runners import (
    run_algebraic_programming_language,
    run_between,
    run_clockwise,
    run_container,
    run_cvnc,
    run_fargo,
    run_flowchart,
    run_forbin_boolean,
    run_inject,
    run_laserfuck,
    run_myscript,
    run_nevermind,
    run_suptiftam,
    run_taglate,
    run_ztoalc,
)


class TestInject:
    """The decision tree of ``skipq`` guards over stored input blocks."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result.

        ``send`` terminates every line it writes and is the only output
        command, so the answer arrives with a newline after it.
        """
        program = boolean.inject(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_inject(program, bits)
            assert got == table[combo] + "\n", f"inputs {bits}"

    def test_every_two_input_table(self) -> None:
        """All sixteen two-input tables build and compute their function."""
        for table in ("".join(t) for t in itertools.product("01", repeat=4)):
            program = boolean.inject(table)
            for combo in range(4):
                bits = [str((combo >> (1 - i)) & 1) for i in range(2)]
                got = run_inject(program, bits)
                assert got == table[combo] + "\n", f"{table} inputs {bits}"

    def test_constant_subtrees_are_folded(self) -> None:
        """A table ignoring its later inputs costs one test, not ``n``.

        The fold is what the shape catalogue asserts of every tree
        generator; measured here directly so a regression names itself.
        """
        one_dependency = len(boolean.inject("00001111"))
        parity = len(boolean.inject("01101001"))
        assert one_dependency < parity / 2

    def test_reads_every_input_before_branching(self) -> None:
        """The reads are hoisted, so every path consumes exactly ``n`` lines.

        The boolean contract requires a constant read count; Inject gets it
        by reading all the bits up front rather than at the tree's nodes.
        """
        program = boolean.inject("0001").splitlines()
        reads = [i for i, line in enumerate(program) if line.startswith("readto")]
        first_branch = next(
            i for i, line in enumerate(program) if line.startswith("skipq")
        )
        assert len(reads) == 2, "one readto per input, and no more"
        assert max(reads) < first_branch, "every read precedes every branch"


class TestSuptiftam:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.suptiftam(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_suptiftam(program, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_minterm_structure(self) -> None:
        """The program reads one row per input and sums the minterms."""
        program = boolean.suptiftam("0001")
        assert program.startswith("sum=0\np=1\nfd mulStep :x")
        assert program.count("%-[read]22%") == 2  # one normalized read per input
        assert program.count("down(:read:)") == 2
        assert program.endswith("term=sum")

    def test_constant_tables_skip_the_minterms(self) -> None:
        """A constant-zero table has no minterm rows at all."""
        program = boolean.suptiftam("0000")
        assert "mulStep(:p:)if(p)" not in program

    def test_a_dense_table_is_summed_over_its_zeros(self) -> None:
        """More ones than zeros costs less summed the other way and inverted.

        An all-ones table is the interesting case: it complements to no
        minterms at all, leaving ``sum`` at 0, and the inversion turns that
        into the 1 it should print -- so it needs no special-casing the way
        a gate-network generator's constant table does.
        """
        assert "term=%-[1]sum%" in boolean.suptiftam("1111")
        assert "mulStep(:p:)if(p)" not in boolean.suptiftam("1111")
        assert "term=sum" in boolean.suptiftam("0001")  # sparse: drawn directly
        # and both still compute their table
        for table in ("1111", "11111110"):
            n = len(table).bit_length() - 1
            program = boolean.suptiftam(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_suptiftam(program, bits) == table[combo]

    def test_bit_names_extend_beyond_the_alphabet(self) -> None:
        """Identifiers are alphabetical, so past 'z' the names grow a prefix."""
        from esolangs.tools.boolean.other import _suptiftam_bit

        assert _suptiftam_bit(0) == "b"
        assert _suptiftam_bit(24) == "z"
        assert _suptiftam_bit(25) == "bb"
        assert _suptiftam_bit(49) == "bz"
        assert _suptiftam_bit(50) == "bbb"

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.suptiftam("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.suptiftam("02")


class TestForbinBoolean:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.forbin_boolean(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_forbin_boolean(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_uses_the_lsb_of_each_input(self) -> None:
        """Each input is read as 8 bits and only the LSB drives the tree."""
        program = boolean.forbin_boolean("01")
        # one 8-variable read, then a decision tree that prints '1' for bit 1
        assert "i0_0,i0_1,i0_2,i0_3,i0_4,i0_5,i0_6,i0_7 = (in 0);" in program

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice returns its answer instead of branching further."""
        assert boolean.forbin_boolean("11111111").count("return 0;") == 1
        assert boolean.forbin_boolean("11110000").count("return 0;") == 2
        assert boolean.forbin_boolean("10010110").count("return 0;") == 8

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.forbin_boolean("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.forbin_boolean("02")


class TestCvnc:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.cvnc(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_cvnc(program, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_a_table_that_folds_nothing_is_a_full_tree(self) -> None:
        """Parity folds nowhere, so it keeps a leaf per row."""
        program = boolean.cvnc("01101001")
        assert program.count("fu") == 8  # one leaf per row
        assert program.count("\u0270\u030ao") == 7  # one branch per interior node

    def test_a_constant_table_folds_to_one_leaf_but_keeps_its_reads(self) -> None:
        """Folding drops the branches, never the reads."""
        for table in ("00000000", "11111111"):
            program = boolean.cvnc(table)
            assert program.count("so") == 3  # still three inputs consumed
            assert program.count("\u0270\u030ao") == 0  # nothing left to branch on
            assert program.count("fu") == 1  # one leaf for the whole table

    def test_a_one_dependency_table_costs_two_leaves(self) -> None:
        """Depending on one input collapses the other two levels.

        This table is where the hoisted build wins, so the three reads are
        the load block's and appear once each rather than once per folded
        path.  Either way only the root branches and only two leaves remain.
        """
        program = boolean.cvnc("11110000")
        assert program.count("fu") == 2
        assert program.count("\u0270\u030ao") == 1  # only the root still branches
        assert program.count("so") == 3  # three inputs, read once each
        for combo in range(8):
            bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
            assert run_cvnc(program, bits) == "11110000"[combo]

    def test_folding_shortens_the_program(self) -> None:
        assert len(boolean.cvnc("00000000")) < len(boolean.cvnc("01101001"))

    def test_the_halting_goto_covers_every_arity_the_generator_emits(self) -> None:
        """The gadget's reach is the generator's arity bound, and is checked.

        The goto lands at a fixed offset, so a program longer than that
        offset would jump back *into itself* instead of halting.  The
        generator raises rather than emit one, and the reach is chosen so
        that no arity it can practically be asked for trips the guard.
        """
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        reach = module._HALT_REACH  # noqa: SLF001

        # parity is the table that folds nothing, so it is the worst case
        for n in range(1, 9):
            table = "01" * (2**n // 2)
            assert len(boolean.cvnc(table)) < reach, f"n={n}"

    def test_a_program_outgrowing_the_goto_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The guard raises rather than emitting a self-re-entering program.

        The reach is far past any table worth generating, so the guard is
        reached by shrinking it rather than by building a vast table.
        """
        # ``esolangs.tools.boolean.cvnc`` resolves to the re-exported
        # *function*, so the module has to be fetched by name.
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        monkeypatch.setattr(module, "_HALT_REACH", 10)
        with pytest.raises(ValueError, match="outgrew"):
            module.cvnc("01")

    def test_every_leaf_ends_by_halting(self) -> None:
        """Without the halting goto a then-arm falls into its own loop end."""
        program = boolean.cvnc("0110")
        assert program.count("\u0279i") == program.count("fu")

    def test_a_zero_input_table_is_refused(self) -> None:
        """A one-entry table is a constant, not a function of any input."""
        for bit in ("0", "1"):
            with pytest.raises(ValueError, match="at least one input"):
                boolean.cvnc(bit)

    def test_the_hoisted_build_reorders_a_table_the_stream_order_cannot_fold(
        self,
    ) -> None:
        """A table folding only on its *last* input is what the reorder is for.

        ``10101010`` is ``11110000``'s function with the inputs renamed, so
        the node-read tree cannot fold it at the root while the hoisted one
        tests input 2 first and folds after a single branch.  The win has to
        show up as a shorter program, not merely a different one.
        """
        program = boolean.cvnc("10101010")
        assert program.count("fu") == 2  # two leaves, as the reorder intends
        assert program.count("ɰ̊o") == 1
        # The unreordered node-read tree over the same table folds only at the
        # bottom, so it costs a leaf per row.
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        unreordered = module._tree("10101010", 0)  # noqa: SLF001
        assert unreordered.count("fu") == 8
        assert len(program) < len(unreordered)

    def test_the_hoisted_build_stores_and_fetches_rather_than_rotating(self) -> None:
        """The bridge between read order and test order is the deque's ends."""
        program = boolean.cvnc("10101010")
        # Every input is read once and pushed to an end in the same syllable.
        assert program.count("so") == 3
        assert program.count("som") + program.count("son") == 3
        # The one surviving node fetches rather than reads.
        assert program.count("cuŋ") + program.count("cuɲ") == 1

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_computes_its_function(self, n: int) -> None:
        """Exhaustive over both constructions, since either may be returned."""
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            program = boolean.cvnc(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_cvnc(program, bits) == table[combo], f"{table} {bits}"

    def test_choosing_between_the_builds_never_grows_a_program(self) -> None:
        """The hoist has a price, so it is a candidate and not a replacement.

        Parity is the table it loses on: nothing folds, so the load block's
        nasals and the per-node fetch are paid for with no fold to show for
        them, and the node-read tree must still be the one returned.
        """
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        for value in range(2**8):
            table = bin(value)[2:].zfill(8)
            assert len(boolean.cvnc(table)) <= len(module._tree(table, 0))  # noqa: SLF001
        # and parity specifically keeps the node-read build
        assert boolean.cvnc("01101001") == module._tree("01101001", 0)  # noqa: SLF001

    def test_an_unservable_order_is_skipped_rather_than_mispriced(self) -> None:
        """The deque serves the unimodal orders; the rest return no program.

        ``best_input_order`` reads an empty candidate as "this order could
        not be built" and skips it, so returning one is how an unservable
        order declines. Substituting some other program would let it win on
        a length it never paid.
        """
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        # (0, 2, 1, 3) is the smallest non-unimodal permutation.
        assert module._deque_schedule((0, 2, 1, 3)) is None  # noqa: SLF001
        assert module._hoisted_candidate("0" * 16, (0, 2, 1, 3)) == ""  # noqa: SLF001
        # The identity is always unimodal, so a candidate always exists.
        assert module._deque_schedule((0, 1, 2, 3)) is not None  # noqa: SLF001

    def test_a_table_folding_at_its_root_normalizes_the_last_read(self) -> None:
        """The hoisted build's folded root still holds an unpredictable bit.

        No branch has run, so the accumulator is whatever the load block read
        last rather than a bit the tree chose.  Without the ``cə`` the leaf
        climbs from that and prints one too many for a 1 input.
        """
        module = importlib.import_module("esolangs.tools.boolean.cvnc")
        program = module._hoisted("00", (0,))  # noqa: SLF001
        assert program is not None
        assert "cə" in program
        for bit in ("0", "1"):
            assert run_cvnc(program, [bit]) == "0"


class TestFargo:
    """The Fargo boolean generator: an algebraic normal form, not a tree."""

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_every_table_at_small_arity(self, n: int) -> None:
        """Exhaustive: every table, every input combination."""
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.fargo(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                got = run_fargo(program, bits)
                assert got == table[combo], f"table {table} inputs {bits}"

    @pytest.mark.parametrize("n", [4, 5, 8])
    def test_higher_arity_tables(self, n: int) -> None:
        """The construction is uncapped: no arity limit, no search."""
        rng = random.Random(20260830 + n)
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(2**n))
            program = boolean.fargo(table)
            for _ in range(10):
                combo = rng.randrange(2**n)
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_fargo(program, bits) == table[combo]

    def test_constant_tables_need_no_reads(self) -> None:
        """A constant table is its degree-zero coefficient alone."""
        assert boolean.fargo("00000000") == "% 0 0\n$\n"
        assert boolean.fargo("11111111") == "% 0 1\n$\n"

    def test_parity_is_one_term_per_input(self) -> None:
        """Parity's ANF is the sum of the single-variable terms."""
        assert boolean.fargo("01101001") == "% 0 ^ ^ @ 0 @ 1 @ 10\n$\n"

    def test_parity_grows_linearly_not_exponentially(self) -> None:
        """The size tracks algebraic complexity, so parity is O(n log n).

        This is the property that makes Fargo's generator unlike the
        tree-shaped ones: a decision tree spends O(2**n) on parity, the
        table that folds nothing.  Parity's ANF is one single-variable
        term per input, so each extra input adds one ``^ @ i`` -- a
        constant plus the index's own binary width, which is why the
        steps widen by one every time ``i`` gains a digit rather than
        staying exactly equal.
        """
        sizes = [
            len(boolean.fargo("".join(str(bin(r).count("1") % 2) for r in range(2**n))))
            for n in (2, 4, 6, 8)
        ]
        gaps = [b - a for a, b in itertools.pairwise(sizes)]
        # Each step of two inputs costs a bounded amount, nowhere near the
        # doubling per input a decision tree would pay.
        assert all(12 <= gap <= 20 for gap in gaps), f"not linear: {sizes}"
        # A decision tree over n == 8 would be thousands of characters.
        assert sizes[-1] < 100, f"growing too fast: {sizes}"

    def test_a_one_dependency_table_folds(self) -> None:
        """One term whatever the arity, which is what the catalogue checks."""
        assert boolean.fargo("11110000") == "% 0 ^ 1 @ 10\n$\n"
        assert len(boolean.fargo("11110000")) < len(boolean.fargo("01101001"))

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.fargo("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.fargo("02")


class TestFlowchart:
    """The Flowchart boolean generator (works for arbitrary n)."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0111", 2),  # OR
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("01101001", 3),  # XOR3
            ("11111110", 3),  # NAND3
            ("0110100110010110", 4),  # XOR4
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result.

        The read count is checked alongside the answer: a folded leaf
        carries the reads of the levels it skipped, so a heavily folding
        table (the constants, AND4) must still consume all ``n`` inputs.
        Without those the drawing would be correct and the program would
        still leave the caller's remaining bits on the stream.
        """
        import contextlib

        from esolangs.interpreters.grid_based.flowchart import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        program = boolean.flowchart(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_flowchart(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"
        io = ScriptedIO("0\n" * (n + 4))
        with contextlib.suppress(Exception, SystemExit):
            run_until_halt_or_cycle(_Machine(program.splitlines(), io))
        assert io.position() == n, (
            f"table {table} consumed {io.position()} inputs, expected {n}"
        )

    def test_tree_depth_matches_input_count(self) -> None:
        """One ``/ /`` read node sits on each path from entry to a leaf."""
        program = boolean.flowchart("0110100110010110")
        assert program.count("< >") == 15  # 2**4 - 1 internal nodes
        assert program.count("(( ))") == 16  # 2**4 leaves

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice is one leaf, and takes one column band.

        The leaves keep their pitch but are handed out as the walk reaches
        them, so a folded subtree narrows the drawing rather than leaving a
        gap where its rows would have been.
        """
        assert boolean.flowchart("11111111").count("(( ))") == 1
        assert boolean.flowchart("11110000").count("(( ))") == 2
        assert boolean.flowchart("10010110").count("(( ))") == 8  # no fold
        # a constant table needs no switch at all
        assert boolean.flowchart("11111111").count("< >") == 0
        assert boolean.flowchart("11110000").count("< >") == 1

    @pytest.mark.parametrize(
        "table", ["01", "0001", "01101001", "0110100110010110", "1000000000000000"]
    )
    def test_vertical_rails_meet_node_middles(self, table: str) -> None:
        """Every ``│`` connects to the middle of the node above and below it.

        The wiki asks that "vertical paths connecting into a node are expected
        to connect to the middle of the node", and all three of its worked
        examples honour it.  The interpreter is deliberately lenient about
        this -- it enters a node through any cell of its box, which is why an
        earlier, misdrawn version of this tree still computed the right table
        -- so nothing else would catch the drawing drifting off centre.

        The rule is about vertical rails only: the Kolakoski example's top row
        chains nodes horizontally (``( )─[ }─\\[ ]/``), attaching at their end
        cells rather than their middles.
        """
        from esolangs.interpreters.grid_based.flowchart import _Machine

        machine = _Machine(boolean.flowchart(table).splitlines(), IO())
        for row, line in enumerate(machine.grid):
            for col, char in enumerate(line):
                if char != "│":
                    continue
                for neighbour in (row - 1, row + 1):
                    node = machine.nodes.get((neighbour, col))
                    if node is None:
                        continue
                    spelling, start = node
                    middle = start + len(spelling) // 2
                    assert col == middle, (
                        f"rail at ({col}, {row}) meets {spelling!r} at column {col}, "
                        f"but its middle is column {middle}"
                    )

    def test_each_run_reads_exactly_n_bits(self) -> None:
        """The drawn read nodes outnumber the reads any one run performs.

        A depth-4 tree draws 15 ``/ /`` nodes, but a run walks a single
        root-to-leaf path and consumes exactly 4 bits, so the duplication is
        spatial rather than a bit being read more than once (see the
        generator's docstring on why the parameterized once-only embedding
        rule does not apply to an input-reading generator).
        """
        program = boolean.flowchart("0110100110010110")
        assert program.count("/ /") == 15

        consumed = 0

        class _CountingIO(IO):
            def input_str(self, _prompt: str = "Input: ") -> str:
                nonlocal consumed
                consumed += 1
                return "1"

            def print_str(self, text: str) -> None:
                pass

        from esolangs.interpreters.grid_based.flowchart import run as fc_run

        fc_run(program.splitlines(), _CountingIO())
        assert consumed == 4

    def test_rejects_a_malformed_table(self) -> None:
        """A table whose length is not a power of two is rejected."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.flowchart("011")


class TestBetween:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.between(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_between(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_structure(self) -> None:
        """One declare/read/normalize triplet per input, one branch per node."""
        program = boolean.between("0110")
        lines = program.splitlines()
        assert lines[:3] == ["'0'v.", "[0]i.", "[0]s|[0]c.|"]
        # XOR has no constant slice above a single row, so nothing folds and
        # every combination keeps its own leaf.
        assert lines.count(".x.") == 4

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice becomes one leaf instead of branching further.

        The jump addresses come from a second walk over the tree, so this
        also covers the two walks agreeing: a leaf count that matched while
        the addresses did not would still run the wrong branch, which
        :meth:`test_truth_table` would catch.
        """
        assert boolean.between("11111111").count(".x.") == 1
        assert boolean.between("11110000").count(".x.") == 2
        assert boolean.between("10010110").count(".x.") == 8  # parity: no fold

    def test_mismatched_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.between("011")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.between("0123")


class TestNevermind:
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
        program = boolean.nevermind(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_nevermind(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function reads one input and branches on it."""
        program = boolean.nevermind("10")
        assert program.startswith("input,?")
        assert "if,$a,==,0" in program
        assert program.count("endif") == 2

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints its answer instead of branching further."""
        assert boolean.nevermind("11111111").count("print,") == 1
        assert boolean.nevermind("11110000").count("print,") == 2
        assert boolean.nevermind("10010110").count("print,") == 8  # no fold


class TestContainer:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT
            ("10", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.container(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """The program reads n inputs and keeps one survivor per row."""
        program = boolean.container("0110")
        assert program.startswith("T:\n+1 T>=T")
        assert ":" in program.splitlines()[:4]  # the empty-named reader
        assert program.count("S") >= 4  # a survivor per row
        assert program.count("PRINT:") == 1

    def test_dense_tables_evaluate_the_complement(self) -> None:
        """A dense table is summed from its zero rows and inverted.

        ``OUT`` costs one ``+1 S{row}>=Gout`` line per row the table sends
        to 1, so before this the length rose with the ones-count all the way
        to the all-ones table.  Now it peaks at half and falls back
        symmetrically, which is the signature of taking whichever row-set is
        smaller.
        """
        lengths = [len(boolean.container("1" * k + "0" * (8 - k))) for k in range(9)]
        assert lengths[4] == max(lengths)  # four ones is the worst case
        assert lengths == lengths[::-1]  # and the curve is symmetric

    @pytest.mark.parametrize("table", ["11111110", "11111111", "1110", "0111"])
    def test_complemented_tables_still_compute(self, table: str) -> None:
        """The inverted form answers the original table.

        It starts ``OUT`` at 49 and subtracts one per surviving zero row, so
        the printed byte is ``49 - S``; the container clamp at zero never
        bites, since the value stays at 48 or 49.
        """
        n = (len(table) - 1).bit_length()
        program = boolean.container(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.container("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.container("02")


class TestZtoalc:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("00000001", 3),  # AND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.ztoalc_l_boolean(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_ztoalc(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to two inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.ztoalc_l_boolean(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_ztoalc(program, [str(b) for b in bits]) == table[combo]

    def test_structure(self) -> None:
        """The program is a branch-free array lookup on a Collatz trajectory."""
        program = boolean.ztoalc_l_boolean("0110")
        lines = program.splitlines()
        assert lines[0].strip().isdigit()  # line 1 is the starting value
        assert any(line.strip().startswith("t = [") for line in lines)
        assert any(line.strip().startswith("print") for line in lines)
        # The construction branches on nothing, so the tree's jumps are gone.
        assert not any("jump" in line for line in lines)

    def test_commands_are_placed_without_collisions(self) -> None:
        """Every command occupies its own line, in trajectory order.

        This is the placement guarantee stated directly: a Collatz
        trajectory visits distinct values until it reaches 1, so the
        commands land on distinct lines and each executes exactly once.
        """
        from esolangs.tools.boolean.ztoalc_l import _collatz_prefix, _commands

        for table in ("0110", "1010001000011000", "0110100110010110"):
            n = len(table).bit_length() - 1
            cmds = _commands(table, n)
            program = boolean.ztoalc_l_boolean(table)
            start = int(program.splitlines()[0])
            values = _collatz_prefix(start, len(cmds))
            assert len(set(values)) == len(values), table
            assert 1 not in values, table
            emitted = program.splitlines()
            assert [emitted[v - 1] for v in values] == cmds, table

    def test_xor4_is_small(self) -> None:
        """XOR4 renders compactly, where the old linear fallback was huge.

        The removed fallback placed a branch-free program on the pure
        power-of-two descent, so its ``2**L`` lines put XOR4 at 524,288.  A
        trajectory's peak grows far slower, and the same program fits in
        hundreds of lines.
        """
        table = "0110100110010110"
        program = boolean.ztoalc_l_boolean(table)
        assert len(program.splitlines()) < 1000
        for combo in range(16):
            bits = [str((combo >> (3 - i)) & 1) for i in range(4)]
            assert run_ztoalc(program, bits) == table[combo], f"inputs {bits}"

    def test_dense_non_symmetric_table(self) -> None:
        """A dense non-symmetric table renders; it once could not be placed.

        Neither the tree (under any input order) nor the popcount-symmetric
        fallback could place this table, so the generator refused it.  The
        lookup construction has no placement problem to fail at.
        """
        table = "1010001000011000"
        program = boolean.ztoalc_l_boolean(table)
        for combo in range(16):
            bits = [str((combo >> (3 - i)) & 1) for i in range(4)]
            assert run_ztoalc(program, bits) == table[combo], f"inputs {bits}"

    def test_constant_table_skips_the_lookup(self) -> None:
        """A constant table prints its constant, still draining its inputs."""
        for n, bit in ((2, "0"), (3, "1")):
            table = bit * (2**n)
            program = boolean.ztoalc_l_boolean(table)
            assert "t = [" not in program
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_ztoalc(program, bits) == bit

    def test_zero_input_table_is_refused(self) -> None:
        """A single-entry table is a constant, not a function of any input."""
        for bit in ("0", "1"):
            with pytest.raises(ValueError, match="at least one input"):
                boolean.ztoalc_l_boolean(bit)

    def test_table_past_the_anchor_table_is_refused(self) -> None:
        """A table needing more steps than any committed anchor is refused."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.ztoalc_l")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "ANCHORS", [(1, 2), (8, 6)])
            with pytest.raises(ValueError, match="longest committed anchor"):
                module.ztoalc_l_boolean("0110")

    def test_table_needing_too_many_lines_is_refused(self) -> None:
        """A table whose trajectory peaks past the line limit is refused."""
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.ztoalc_l")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_MAX_LINES", 8)
            with pytest.raises(ValueError, match="past the"):
                module.ztoalc_l_boolean("0110")

    def test_wrong_length_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.ztoalc_l_boolean("011")

    def test_invalid_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.ztoalc_l_boolean("02")


class TestClockwise:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),
            ("10", 1),
            ("00", 1),
            ("11", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("00000001", 3),  # AND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination prints the result as an ASCII digit."""
        program = boolean.clockwise(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_clockwise(program, bits)
            assert got == table[combo], f"inputs {bits}"

    def test_ring_starts_at_origin(self) -> None:
        """The program is a closed ring whose pointer starts at (0, 0)."""
        program = boolean.clockwise("0110")
        lines = program.splitlines()
        assert lines[0][0] == " "
        assert run_clockwise(program, ["1", "0"]) == "1"  # XOR(1, 0)

    @pytest.mark.parametrize(("table", "n"), [("0001", 2), ("01101001", 3)])
    def test_tree_sits_against_the_left_edge(self, table: str, n: int) -> None:
        """No column is dead: the spine starts as far left as it can.

        The tree's turns are relative, so its absolute column never
        matters; a spine further right is pure padding.  It only has to
        clear the ``2**(n + 1) - 1`` columns its leftward branches span,
        leaving column 0 for the closing corner.
        """
        program = boolean.clockwise(table)
        rows = program.splitlines()
        width = max(len(row) for row in rows)
        grid = [row.ljust(width) for row in rows]
        dead = [x for x in range(width) if all(row[x] == " " for row in grid)]
        assert not dead, f"dead columns {dead}"
        assert width == 2 ** (n + 1) + 1

    def test_constant_subtrees_narrow_the_ring(self) -> None:
        """A folded subtree spends no displacement, so the grid narrows.

        Width grows as ``2 ** (n + 1)``, and a node only displaces its
        one-branch when it actually branches -- so a table whose subtrees
        collapse needs fewer columns.  A scattered table folds nothing and
        must be unchanged.
        """
        scattered = boolean.clockwise("10010110")
        for table in ("11111111", "11110000"):
            folded = boolean.clockwise(table)
            assert len(folded) < len(scattered), table
        assert len(boolean.clockwise("11001100")) < len(scattered)

    def test_folded_column_still_reads_every_input(self) -> None:
        """A folded column keeps the reads it skipped branching on.

        Clockwise reads *inside* the tree -- seven ``.`` per level -- so a
        folded leaf that dropped them would consume fewer inputs than an
        unfolded one and desync a caller feeding several programs from one
        stream.  Every column therefore carries ``7 * n`` reads.
        """
        for table in ("11111111", "11110000", "11001100"):
            n = len(table).bit_length() - 1
            program = boolean.clockwise(table)
            rows = program.splitlines()
            width = max(len(row) for row in rows)
            grid = [row.ljust(width) for row in rows]
            columns = [sum(1 for row in grid if row[x] == ".") for x in range(width)]
            # the deepest column reads every input; none reads more
            assert max(columns) <= 7 * n, table
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_clockwise(program, bits) == table[combo], (table, bits)

    def test_folding_never_grows_the_program(self) -> None:
        """The hoist floor: narrowing must not cost more than it saves.

        Hoisting the root's seven reads onto row 0 retires seven rows, but
        needs seven free columns left of the root.  At ``n == 2`` a tree
        folded to seven columns loses that and comes out *larger* than the
        unfolded program, so the width never narrows below what the hoist
        needs.
        """
        for n in (1, 2, 3):
            # the alternating table folds nothing at any level, so it is the
            # full-size program every other table must come in at or under
            unfolded = len(boolean.clockwise("10" * (2 ** (n - 1))))
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                assert len(boolean.clockwise(table)) <= unfolded, table


class TestTaglate:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),
            ("01", 1),
            ("10", 1),
            ("11", 1),
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("00000001", 3),  # majority
            ("0000000000000001", 4),  # 4-AND
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            # Odd n > 1 uses a ghost digit (fake zero first input)
            inputs = (
                ["0"] + [str(b) for b in bits]
                if n % 2 == 1 and n > 1
                else [str(b) for b in bits]
            )
            got = run_taglate(program, inputs)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every two-input truth table produces the right result."""
        for table in range(16):
            tt = format(table, "04b")
            for combo in range(4):
                bits = [(combo >> 1) & 1, combo & 1]
                got = run_taglate(boolean.taglate(tt), [str(b) for b in bits])
                assert got == tt[combo], f"{tt} inputs {bits}"

    def test_all_three_input_tables(self) -> None:
        """Every three-input truth table produces the right result."""
        failures = 0
        for table in range(256):
            tt = format(table, "08b")
            program = boolean.taglate(tt)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                inputs = ["0"] + [str(b) for b in bits]  # ghost digit
                got = run_taglate(program, inputs)
                if got != tt[combo]:
                    failures += 1
                    if failures <= 3:
                        print(
                            f"  FAIL {tt} inputs {bits}: "
                            f"got {got!r} expected {tt[combo]!r}"
                        )
        assert failures == 0, f"{failures} failures out of 2048 combos"

    def test_tables_ignoring_inputs_shrink(self) -> None:
        """A table that ignores inputs is emitted as the smaller table.

        Taglate's cost is almost all fixed overhead scaled by the input
        count -- the seed alone is ``2**(n_eff + 2)`` cells -- so dropping
        an input drops a whole tier.  Every table of a given ``n`` used to
        be the same length; now the ones that depend on fewer inputs are
        dramatically shorter.
        """
        full = len(boolean.taglate("10010110"))  # depends on all three
        for table in ("11110000", "11001100", "10101010", "00000000"):
            assert len(boolean.taglate(table)) < full // 10, table

    def test_gapped_dependencies_reduce_without_reordering_inputs(self) -> None:
        """Every n=3 function of inputs 0 and 2 uses the small program.

        The discarded middle input is read after the reduced program's first
        read.  Its rotate-and-drop restores that exact intermediate queue,
        rather than shifting the arithmetic slots a later reduce addresses.
        """
        tables = (
            "00000101",
            "00001010",
            "01010000",
            "01011010",
            "01011111",
            "10100000",
            "10100101",
            "10101111",
            "11110101",
            "11111010",
        )
        full = len(boolean.taglate("10010110"))
        for table in tables:
            program = boolean.taglate(table)
            assert len(program) < full, table
            assert program.count("h") == 4, table  # ghost plus all three inputs
            for combo in range(8):
                bits = [str((combo >> shift) & 1) for shift in (2, 1, 0)]
                assert run_taglate(program, ["0", *bits]) == table[combo], (table, bits)

    def test_reduced_programs_still_read_every_input(self) -> None:
        """A reduced program consumes the inputs it no longer uses.

        The ignored ones are read and discarded (``h`` appends to the
        queue's tail, ``e`` once per queued cell rotates it to the front,
        ``f`` drops it), so the queue is left exactly as it was and a caller
        feeding several programs from one stream stays in sync.  Odd ``n``
        above 1 also takes a leading ghost digit, which is one more read.
        """
        for n in (1, 2, 3, 4):
            expected = n + (1 if n % 2 == 1 and n > 1 else 0)
            for table in (
                "1" * 2**n,
                "1" * 2 ** (n - 1) + "0" * 2 ** (n - 1),
                ("10" * 2**n)[: 2**n],
            ):
                program = boolean.taglate(table)
                assert program.count("h") == expected, (n, table)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1111111100000000", 4),  # depends on input 0
            ("1111000011110000", 4),  # input 1
            ("1010101010101010", 4),  # input 3
            ("1111111111111111", 4),  # none at all
        ],
    )
    def test_reduced_tables_compute_past_three_inputs(self, table: str, n: int) -> None:
        """The reduction stays correct deeper than the exhaustive sweep."""
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            ghost = ["0"] if n % 2 == 1 and n > 1 else []
            got = run_taglate(program, ghost + [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            # depends on inputs 0-2, so the window widens rightward to 0-3
            ("0000000000000011", 4),
            # depends on inputs 1-3, which has no room on the right, so the
            # window widens leftward to 0-3 instead
            ("0000000100000001", 4),
        ],
    )
    def test_odd_dependency_sets_widen_to_stay_even(self, table: str, n: int) -> None:
        """An odd-sized window takes one more ignored input, either side.

        The reduced program ghost-pads itself at odd arity, so it would
        expect an input the caller's stream does not carry.  Widening the
        window by one adjacent *ignored* input keeps the reduced table even
        and the read count honest -- and it has to work at both ends, since
        a set already touching the last input has no room on the right.
        """
        program = boolean.taglate(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            ghost = ["0"] if n % 2 == 1 and n > 1 else []
            got = run_taglate(program, ghost + [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.taglate("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.taglate("0120")


class TestThreeX:
    def test_identity_program_structure(self) -> None:
        """The 01 table reads a bit and stores it before printing."""
        program = boolean.three_x("01")
        assert program.startswith("?")
        assert program.endswith("!")

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than the identity order's program."""
        from esolangs.tools.boolean.other import _three_x_ordered

        for i in range(256):
            table = format(i, "08b")
            identity = _three_x_ordered(table, (0, 1, 2))
            assert len(boolean.three_x(table)) <= len(identity)

    def test_unimproved_tables_keep_their_emission(self) -> None:
        """A table no reorder helps emits exactly what it emitted before.

        ``best_input_order`` tries the identity first and keeps it on a tie,
        so reordering can only shrink a program, never churn one.  A constant
        table has no override blocks at all, so no order can beat it.
        """
        from esolangs.tools.boolean.other import _three_x_ordered

        for table in ("0" * 8, "1" * 8):
            assert boolean.three_x(table) == _three_x_ordered(table, (0, 1, 2))

    def test_reads_stay_in_stream_order(self) -> None:
        """Only the store target moves, so the input stream is consumed the same.

        The reorder is spelled in which variable each ``?`` stores into, not
        in when the reads happen: every build reads its ``n`` inputs up front,
        one ``?`` each, whatever order the tree tests them in.
        """
        from esolangs.tools.boolean.other import _three_x_ordered

        table = "00010111"
        for perm in ((0, 1, 2), (2, 1, 0), (1, 2, 0)):
            program = _three_x_ordered(table, perm)
            head = program[: program.index("(")] if "(" in program else program
            assert head.count("?") == 3
            # the reads are the first thing the program does
            assert program.startswith("?")

    def test_every_input_order_computes_the_table(self) -> None:
        """The permuted build computes the original table on the original stream."""
        import itertools

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.three_x import run
        from esolangs.tools.boolean.other import _three_x_ordered

        def permuted(table: str, perm: tuple[int, ...]) -> str:
            out = []
            for row in range(8):
                src = 0
                for k in range(3):
                    src |= ((row >> (2 - k)) & 1) << (2 - perm[k])
                out.append(table[src])
            return "".join(out)

        for table in ("00010111", "01101001", "11110000", "10101010"):
            for perm in itertools.permutations(range(3)):
                program = _three_x_ordered(permuted(table, perm), perm)
                for combo in range(8):
                    bits = [(combo >> (2 - k)) & 1 for k in range(3)]
                    io = ScriptedIO("\n".join(str(b) for b in bits) + "\n")
                    run(program, io)
                    assert io.getvalue().strip() == table[combo], f"{table} {perm}"

    def test_wrong_length_truth_table_rejected(self) -> None:
        """A truth table of the wrong length is malformed."""
        with pytest.raises(ValueError, match="entries"):
            boolean.three_x("011")

    def test_invalid_truth_table_chars_rejected(self) -> None:
        """A truth table with non-0/1 characters is malformed."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.three_x("02")

    def test_uses_input_variables(self) -> None:
        """Each input bit is read into a distinct variable."""
        program = boolean.three_x("0001")
        assert program.count("?") == 2
        assert "333x" in program  # the constant-0 encoding appears
        assert "3333x3x" in program  # the constant-1 encoding appears

    def test_constant_table_has_no_override_blocks(self) -> None:
        """When every row equals the default, no ( ... ) guards are emitted."""
        assert "(" not in boolean.three_x("0" * 4)
        assert "(" not in boolean.three_x("1" * 4)

    def test_majority_default_handles_zero_row(self) -> None:
        """A zero row differing from a majority-1 default still overrides it."""
        program = boolean.three_x("0110")  # XOR: two 1s, two 0s
        assert program.startswith("?")
        assert program.endswith("!")
        assert "(" in program  # the zero row needs an override block

    def test_scales_to_more_inputs(self) -> None:
        """The generator handles n beyond the built-in constants."""
        program = boolean.three_x("0" * (2**7))
        assert program.count("?") == 7

    def test_shared_tree_prefix_sharing(self) -> None:
        """Differing combos share prefix guards instead of repeating them."""
        # top-half n=5: 16 zero-rows all share MSB=0.  A full tree has
        # 31 guard nodes; independent chains would emit 16 * 5 = 80.
        program = boolean.three_x("0" * 16 + "1" * 16)
        assert program.count("(") < 40

    def test_digit_constant_encodings(self) -> None:
        """The base-3 digit seeds are the closed-form minimal programs."""
        from esolangs.tools.boolean import other

        assert other._const(0) == "333x"  # noqa: SLF001
        assert other._const(1) == "3333x3x"  # noqa: SLF001
        assert other._const(2) == "3333x3x3333x3x3x"  # noqa: SLF001

    def test_base_three_digits_accumulate(self) -> None:
        """Each base-3 digit past the first appends the 3v+d affine step."""
        from esolangs.tools.boolean import other

        # 12 is "110" in base 3: seed 1, then d=1, then d=0.  Each transform
        # adds exactly one `#` (the swap before the `x`), and no seed has one.
        twelve = other._const(12)  # noqa: SLF001
        assert twelve.startswith(other._const(1))  # noqa: SLF001
        assert twelve.count("#") == 2

    def test_formula_scales_logarithmically(self) -> None:
        """The closed form grows with the digit count, not the value."""
        from esolangs.tools.boolean import other

        small, large = other._const(100), other._const(1_000_000)  # noqa: SLF001
        assert len(small) < 120  # 100 is "10201": 5 digits
        assert len(large) < 350  # 1_000_000 is 13 base-3 digits
        assert len(large) < len(small) * 4


class TestLaserFuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("00000001", 3),  # AND3
            ("1111111100000000", 4),  # top half
            ("0110100110010110", 4),  # XOR4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.laserfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"inputs {bits} heading {heading}"

    # n=3 is 256 tables at 2.0s, over the fast run's one-second budget;
    # n=1 and n=2 are 16 tables between them and stay well under it.
    @pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.slow)])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.laserfuck(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_laserfuck(program, [str(b) for b in bits], 3)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_funnel_is_heading_independent(self) -> None:
        """Every initial heading reaches the tree on the top row."""
        program = boolean.laserfuck("0110")
        for heading in range(4):
            assert run_laserfuck(program, ["1", "0"], heading) == "1"

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        """The tree splits in whichever order folds most, not input order.

        ``10101010`` depends on its last input alone, so it folds nothing
        splitting most-significant-first and everything once that input is
        tested at the root.  The reorder costs only the walk that puts the
        bit in the cell the root tests, which is paid once in the reader
        rather than per node -- so the two one-dependency tables come out
        the same size.
        """
        scattered = len(boolean.laserfuck("10101010"))
        aligned = len(boolean.laserfuck("11110000"))
        parity = len(boolean.laserfuck("01101001"))
        assert scattered == aligned
        assert aligned < parity

    def test_input_reordering_never_grows_a_program(self) -> None:
        """The identity order is built first and ties keep it.

        Parity folds under no order at all, so it has to emit exactly the
        program it emitted before reordering existed -- which is the plain
        read section, one ``,`` per cell stepping rightwards with no walk
        back and forth.
        """
        assert ",>,>," in boolean.laserfuck("01101001")

    def test_wide_tables_do_not_search_every_order(self) -> None:
        """Past the cap only the identity order is built, not ``n!`` of them.

        Seven inputs would be 5040 orders; the search stops at six, so the
        wide table costs one build.  Counting the builds is the assertion
        rather than the timing, since that is what a change to the cap
        would move.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.laserfuck")
        real = module._laserfuck_build  # noqa: SLF001

        for n, table, orders in (
            (3, "01011010", 6),
            (7, ("10" * 64)[:128], 1),
        ):
            built = 0

            def counted(*args: object, _build: object = real, **kwargs: object) -> str:
                nonlocal built
                built += 1
                return _build(*args, **kwargs)  # type: ignore[operator, no-any-return]

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(module, "_laserfuck_build", counted)
                boolean.laserfuck(table)
            assert built == orders, f"n={n} built {built} candidates"

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_programs_compute_the_table(self, table: str) -> None:
        """A reordered program still computes its function, at every heading.

        The cell an input is read into is the *inverse* of the split order:
        a node steps then tests, so level ``k`` tests cell ``k + 1`` and has
        to be handed input ``perm[k]``.  Reading that forward stores the
        right bits in the wrong cells and computes a different function,
        which only running the program catches.
        """
        program = boolean.laserfuck(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == table[combo], f"{table} inputs {bits} heading {heading}"

    def test_reordering_keeps_the_reads_in_stream_order(self) -> None:
        """Reordering moves where a bit is stored, never when it is read.

        The program consumes its input stream exactly as it did before: one
        ``,`` per input, in input order.  What moves is the cell each lands
        in, so the count of reads is what pins this down.
        """
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.laserfuck(table).count(",") == 3

    def test_decimal_output_mode(self) -> None:
        """No ``\\xff`` marker, so the tape dumps as numbers, not bytes.

        Byte mode would print the answer as ``chr(result)``, which is why
        the leaves used to add 48 to reach ASCII ``'0'``/``'1'``.  In decimal
        mode the leaf writes the result itself.
        """
        program = boolean.laserfuck("10")
        assert program.splitlines()[0][0] != "\u00ff"
        assert "\u00ff" not in program

    def test_prints_only_the_answer(self) -> None:
        """The dump is exactly the result: no input cells, no separators.

        The input cells are driven negative by the leaf, and ``dump`` skips
        negative cells, so nothing but the answer survives.
        """
        program = boolean.laserfuck("0001")  # AND2
        for bits, want in (([0, 1], "0"), ([1, 1], "1")):
            got = run_laserfuck(program, [str(b) for b in bits], 3)
            assert got == want, f"inputs {bits}"

    def test_loop_free_tree(self) -> None:
        """The decision tree branches with #, ) and a turning mirror."""
        program = boolean.laserfuck("0110")
        assert "#" in program
        assert ")" in program
        # the tree is mirrored, so a one-branch turns on '/' rather than '\\'
        assert "/" in program

    def test_rejects_bad_table(self) -> None:
        """A truth table of the wrong length is rejected."""
        with pytest.raises(ValueError, match="entries"):
            boolean.laserfuck("011")

    def test_rejects_non_binary(self) -> None:
        """A truth table with a character other than 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.laserfuck("02")

    @pytest.mark.parametrize(
        ("table", "n", "width"),
        [
            # The tree is never folded and grows six columns per node, so the
            # narrowest width a table can honour rises with its input count:
            # roughly 19, 34, and 63 columns for one, two, and three inputs.
            ("01", 1, 20),
            ("01", 1, 40),
            ("10", 1, 80),
            ("0110", 2, 34),
            ("0110", 2, 80),
            ("1000", 2, 120),
            ("01101001", 3, 63),
            ("01101001", 3, 80),
            ("11111110", 3, 120),
        ],
    )
    def test_honours_a_width(self, table: str, n: int, width: int) -> None:
        """``width`` bounds the columns and the table still computes.

        The grid's width is dominated by its straight runs -- 49 columns per
        input reader and another 49 per leaf -- so those fold into zigzags
        that cost rows instead.  The decision tree is not folded: its
        columns carry the descent paths.  Every heading is checked, since
        the fold adds cells the funnel's beam could otherwise land on.
        """
        program = boolean.laserfuck(table, width)
        assert max(len(line) for line in program.split("\n")) <= width
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            for heading in range(4):
                got = run_laserfuck(program, [str(b) for b in bits], heading)
                assert got == str(int(table[combo])), f"{bits} heading {heading}"

    def test_a_width_stands_the_reader_on_end(self) -> None:
        """A width too narrow for the reader rotates it rather than failing.

        Laid flat the rings are one row and forty-odd columns; stood on end
        they are two columns and forty-odd rows, so a width the flat form
        cannot meet is still met.
        """
        table = "01101001"  # XOR3
        natural = max(len(ln) for ln in boolean.laserfuck(table).split("\n"))
        assert natural > 30
        narrow = boolean.laserfuck(table, 30).split("\n")
        assert max(len(ln) for ln in narrow) <= 30
        assert len(narrow) > len(boolean.laserfuck(table).split("\n"))

    def test_the_fold_uses_its_return_rows(self) -> None:
        """A same-character run fills the leftward leg, not just the right.

        A return row's beam travels left, so it may only carry ops that
        read the same in reverse -- which a run of one repeated character
        does.  The boolean generator's readers are rings now, but the fold
        still lays every leaf band and the whole text generator, so the
        fill is exercised directly here.
        """
        grid = [[" "] * 20 for _ in range(2)]
        end_row, end_col = laserfuck_layout.fold(grid, "-" * 30, 0, 3, 20)
        rows = ["".join(line).rstrip() for line in grid]
        assert rows[0].endswith("v")
        assert rows[1].endswith("{")
        assert "-" in rows[1], "the return row should carry the spilled run"
        # 30 ops at width 20: 16 on the segment row, the rest reversed onto
        # the return row, so the run never needs a second segment row.
        assert end_row == 2, "a same-character run should not need a third row"
        assert end_col == laserfuck_layout.MARGIN + 1

    def test_return_rows_only_take_a_same_character_run(self) -> None:
        """The fill stops at the first character that differs.

        A mixed run may only reverse its leading same-character stretch;
        whatever follows has to resume rightwards on the next segment row.
        """
        grid = [[" "] * 20 for _ in range(2)]
        laserfuck_layout.fold(grid, "-" * 30 + ">+++", 0, 3, 20)
        rows = ["".join(line).rstrip() for line in grid]
        body = rows[1][laserfuck_layout.MARGIN + 1 :].rstrip()
        ops = body[:-1].strip() if body.endswith("{") else body.strip()
        assert set(ops) <= {"-"}, f"mixed ops on a return row: {ops!r}"
        # the '>' that broke the run resumes on the next segment row
        assert ">" in rows[2]

    def test_folded_readers_are_rings(self) -> None:
        """The folded reader loops rather than writing 48 '-' per input.

        Two rings sit on the first row: one multiplies 8 by 6 to build the
        48 a ``,`` needs subtracting, the other spends that counter one unit
        at a time across the counter and every input.  Both are one row, so
        the reader costs a fixed two rows however many inputs there are.
        """
        rows = boolean.laserfuck("0110", 80).split("\n")
        # columns 0..2 are the funnel; the reader starts at the margin
        head = rows[0][laserfuck_layout.MARGIN :]
        legs = rows[1][laserfuck_layout.MARGIN :]
        assert head.count("}") == 3, "the reader's own '}' plus one per ring"
        assert head.count("#/)") == 2, "each ring tests its counter"
        assert legs.count("^") == 2, "each ring returns to its own '}'"
        # no 48-'-' run survives anywhere in the program
        assert "-" * 10 not in "\n".join(rows)

    def test_ringed_leaves_sit_on_their_own_descent_rows(self) -> None:
        """A leaf needs no corridor: the beam already arrives moving right.

        The old layout dropped each leaf down a private column into a band
        of its own below the tree.  With the rings the leaf simply follows
        the ``\\`` that turns the beam onto its row -- so no ``v``, no return
        row and no band, and the grid loses better than half its rows.
        """
        # width 50 forces the mirrored form, where the tree hangs below
        rows = boolean.laserfuck("0110", 50).split("\n")
        # 'x' only ever ends a leaf, so the leaf rows are exactly these
        leaves = [line for line in rows if "x" in line]
        assert len(leaves) == 4, "one leaf per input combination"
        # the all-zero leaf rides the row the tree starts on, so only the
        # mirrored, a one-branch's leaf hangs under a '/' and its code runs
        # leftward, so the 'x' comes *before* the turn.  The all-zero leaf
        # shares the tree's first row, which carries the entry mirror too.
        first = min(index for index, line in enumerate(rows) if "x" in line)
        turned = [
            line for index, line in enumerate(rows) if "x" in line and index > first
        ]
        assert len(turned) == 3
        for line in turned:
            assert line.index("x") < line.index("/")
        # nothing below the leaves: no bands, no drop corridors.  Mirrored,
        # a leaf's row ends at its turn rather than at its 'x'.
        assert rows[-1].rstrip()[-1] in "x/"

    def test_a_dropping_beam_crosses_no_other_row_s_code(self) -> None:
        """A one-branch drops through the rows above its own catcher.

        Every ``v`` sends the beam down its column until a mirror faces it
        along a row again; whatever it passes on the way is executed.  The
        rows in between must therefore be blank in that column -- which is
        what lets the tree share rows at all.
        """
        for table in ("0110", "01101001", "0110100110010110"):
            rows = boolean.laserfuck(table, 200).split("\n")
            for index, line in enumerate(rows):
                for column, char in enumerate(line):
                    if char != "v" or index < 3:
                        continue  # the funnel and reader steer themselves
                    # find the '\' that catches this drop
                    below = [
                        (k, rows[k])
                        for k in range(index + 1, len(rows))
                        if column < len(rows[k])
                    ]
                    for k, lower in below:
                        cell = lower[column]
                        if cell in "\\/":
                            break  # caught, as intended
                        assert cell == " ", (
                            f"{table}: beam from row {index} column {column} "
                            f"runs {cell!r} on row {k}"
                        )

    def test_a_wide_grid_runs_the_tree_on_the_reader_s_rows(self) -> None:
        """Given the width, the tree needs no rows of its own at all.

        The beam leaves the reader still moving right, so the cheapest
        thing is to carry straight on: the tree starts in the next column
        along, on the rows the reader is already using.  A width too narrow
        for that falls back to hanging the tree underneath, mirrored.
        """
        wide = boolean.laserfuck("0110", 80).split("\n")
        narrow = boolean.laserfuck("0110", 50).split("\n")
        assert len(wide) < len(narrow), "sharing rows should cost fewer rows"
        assert max(len(line) for line in wide) > max(len(line) for line in narrow)
        # the reader's own first row carries tree code too
        assert "#/)" in wide[0], "the reader's last ring is on row 0"
        assert ">#v)" in wide[0], "and the tree's first node follows it there"

    def test_widths_come_in_bands_not_a_cliff(self) -> None:
        """Each reader block turns on its own, so widths degrade gradually.

        Turning the whole reader at once gave two sizes and nothing in
        between; turning its blocks independently fills the gap, and a
        tighter width buys rows rather than being ignored.
        """
        seen = {
            max(len(line) for line in boolean.laserfuck("0110", width).split("\n"))
            for width in (45, 40, 30, 25, 18)
        }
        assert len(seen) >= 4, f"expected several distinct widths, got {seen}"
        # asking for less never gives more
        widths = [
            max(len(line) for line in boolean.laserfuck("0110", w).split("\n"))
            for w in (45, 40, 30, 25, 18)
        ]
        assert widths == sorted(widths, reverse=True)

    def test_a_narrow_width_beats_the_old_floor(self) -> None:
        """Standing blocks on end reaches widths the flat reader cannot."""
        for table, floor in (("0110", 18), ("01101001", 24)):
            program = boolean.laserfuck(table, floor).split("\n")
            assert max(len(line) for line in program) <= floor

    def test_ringed_leaves_leave_a_zero_answer_alone(self) -> None:
        """Cell 0 is the counter *and* the answer, so zero costs nothing.

        The rings spend the counter down to zero and leave it touched,
        which is exactly what dump() prints for a zero answer -- so a leaf
        writes a '+' only when the answer is one.

        Both tables are constant, so each folds to a single leaf that fits
        on the reader's own row; the '+' is counted over the whole program
        rather than over the rows below the reader, which a folded tree no
        longer occupies.
        """
        zero = boolean.laserfuck("0000", 80)
        ones = boolean.laserfuck("1111", 80)
        assert ones.count("+") == zero.count("+") + 1, "a one costs exactly one '+'"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice becomes one leaf instead of branching further.

        Leaves are the ``x`` that ends each one, so counting those counts
        the leaves: a constant table spends one, two constant halves spend
        two, and a parity table -- which has no constant slice above a
        single row -- still spends one per combination.
        """
        assert boolean.laserfuck("11111111").count("x") == 1
        assert boolean.laserfuck("11110000").count("x") == 2
        assert boolean.laserfuck("10010110").count("x") == 8

    def test_a_table_that_folds_nothing_keeps_the_sized_sweep(self) -> None:
        """Parity's leaves retire each input by its own bit, not flatly.

        Only the cells above a leaf's depth need the flat two-``-``
        retiring; a parity table has no folded leaf, so every cell is one
        its path consumed and every run is sized to the bits.  Reading the
        runs back off each leaf is what pins that -- a leaf reached by
        ``bits`` spends ``bit + 1`` dashes per cell, most recent first.
        """
        program = boolean.laserfuck("10010110")
        leaves = program.split("x")[:-1]
        for path in range(8):
            bits = [(path >> (2 - i)) & 1 for i in range(3)]
            want = "".join("-" * (b + 1) + "<" for b in reversed(bits))
            assert any(leaf.endswith(want) or want in leaf for leaf in leaves), (
                f"no leaf retires {bits} with its sized run {want!r}"
            )

    def test_without_a_width_is_unchanged(self) -> None:
        """The default stays exactly what the generator always produced."""
        for table in ("01", "10", "0110", "01101001"):
            assert boolean.laserfuck(table) == boolean.laserfuck(table, None)

    def test_too_narrow_a_width_is_ignored(self) -> None:
        """A width the tree cannot fit in is ignored rather than raising.

        The tree grows six columns per node and is never folded, so below
        some width there is nothing the fold can do; the generator emits the
        grid it can build instead of failing, matching the rest of the
        width plumbing.
        """
        program = boolean.laserfuck("01101001", 8)
        assert run_laserfuck(program, ["0", "0", "0"], 3) == "0"


class TestMyScript:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.myscript(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_myscript(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice says its answer instead of branching further."""
        assert boolean.myscript("11111111").count("say") == 1
        assert boolean.myscript("11110000").count("say") == 2
        assert boolean.myscript("10010110").count("say") == 8  # parity: no fold

    def test_rejects_bad_table(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            boolean.myscript("011")

    def test_rejects_non_binary(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.myscript("02")


class TestGeneratorEdgePaths:
    """Coverage for validation and helper edge paths in the generators."""

    def test_parameterized_validation(self) -> None:
        """bio/back reject malformed truth tables."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.bio("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            parameterized.bio("0123")
        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.back("011")

    def test_dimensional_tree_validation(self) -> None:
        """The Dimensional decision-tree generator rejects bad truth tables."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.dimensional_tree("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional_tree("0123")

    def test_six_five_helper_edges(self) -> None:
        """The +5 tail of the constant encoder.

        ``_six_five_nav`` was retired with the arithmetic kernel; the folded
        leaf's own hop to cell 1 is a literal ``13``.
        """
        from esolangs.tools.boolean.six_five import _six_five_const

        assert _six_five_const(5) == "5"
        assert _six_five_const(11) == "65"

    def test_six_five_label_rejects_an_unspellable_operand(self) -> None:
        """Operands are one character, so the alphabet runs out at 35.

        ``0-9`` then ``A-Z`` is every character 6-5 reads as a number, which
        caps a 7n/8n operand at 35; past that there is nothing to emit.
        """
        from esolangs.tools.boolean.six_five import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        with pytest.raises(ValueError, match="no operand character for 36"):
            _six_five_label(_SIX_FIVE_MAX_LABEL + 1)


class TestAlgebraicProgrammingLanguage:
    """The minterm-sum generator, whose whole program is one executed line."""

    @staticmethod
    def _run(program: str, n: int, combo: int) -> str:
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        return run_algebraic_programming_language(program, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # not
            ("0001", 2),  # AND2
            ("0111", 2),  # OR2
            ("0110", 2),  # XOR2
            ("01101001", 3),  # parity
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result.

        An executed line prints its result, so the answer arrives with the
        newline that ends the line.
        """
        program = boolean.algebraic_programming_language(table)
        for combo in range(2**n):
            got = self._run(program, n, combo)
            assert got == table[combo] + "\n", f"table {table} combo {combo}"

    def test_every_one_and_two_input_table(self) -> None:
        """All 4 one-input and 16 two-input tables build and compute."""
        for n in (1, 2):
            for table in ("".join(t) for t in itertools.product("01", repeat=2**n)):
                program = boolean.algebraic_programming_language(table)
                for combo in range(2**n):
                    got = self._run(program, n, combo)
                    assert got == table[combo] + "\n", f"{table} combo {combo}"

    def test_every_three_input_table(self) -> None:
        """All 256 three-input tables build and compute their function."""
        for table in ("".join(t) for t in itertools.product("01", repeat=8)):
            program = boolean.algebraic_programming_language(table)
            for combo in range(8):
                got = self._run(program, 3, combo)
                assert got == table[combo] + "\n", f"{table} combo {combo}"

    def test_the_constant_zero_table_still_reads_every_input(self) -> None:
        """A table with no minterms names each input so the reads still happen.

        The boolean contract requires a constant read count, and APL reads
        by *naming*, so the constant-0 program has to name every variable
        even though none of them can change the answer.
        """
        program = boolean.algebraic_programming_language("0000")
        for name in ("a", "b"):
            assert name in program
        for combo in range(4):
            assert self._run(program, 2, combo) == "0\n"

    def test_reads_are_in_ascending_name_order(self) -> None:
        """A variable is read when the line first names it.

        So the emitted line must name ``a`` before ``b`` before ``c``, or
        the harness's inputs would arrive in the wrong slots.
        """
        program = boolean.algebraic_programming_language("01101001")
        line = program.splitlines()[-1]
        firsts = [min(line.index(n) for n in (v,)) for v in "abc"]
        assert firsts == sorted(firsts)

    def test_every_value_stays_zero_or_one(self) -> None:
        """The program prints a bit, not an arbitrary truth value.

        ``!`` returns exactly 0 or 1 and the connectives pass those
        through, so nothing rests on how APL spells a non-zero truth.
        """
        program = boolean.algebraic_programming_language("0110")
        for combo in range(4):
            assert self._run(program, 2, combo).strip() in {"0", "1"}

    def test_the_complement_operator_is_the_wikis_own(self) -> None:
        """The header is the wiki's ``!x`` definition, verbatim."""
        program = boolean.algebraic_programming_language("0001")
        assert program.startswith("!x = {\nx & $0\n$1\n}\n")

    def test_a_one_entry_table_is_refused(self) -> None:
        """A nullary table is a constant, not a function of any input."""
        with pytest.raises(ValueError, match="a one-entry table is a constant"):
            boolean.algebraic_programming_language("0")


class TestAlgebraicProgrammingLanguageShapes:
    """The structural corners of the minterm expansion, at four inputs.

    The exhaustive n<=3 sweep above already covers every shape the
    construction can take -- empty minterm set, full set, and everything
    between -- and the expansion is mechanical rather than searched, so
    sweeping all 65536 four-input tables costs about eight minutes to
    re-cover the same ground.  These four pin the corners instead: the
    two constants, the table that expands to the most terms, and the one
    that expands to the fewest.
    """

    @staticmethod
    def _check(table: str, n: int = 4) -> None:
        program = boolean.algebraic_programming_language(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_algebraic_programming_language(program, bits)
            assert got == table[combo] + "\n", f"{table} inputs {bits}"

    def test_the_all_zero_table(self) -> None:
        """No minterms at all: the constant-zero branch."""
        self._check("0" * 16)

    def test_the_all_one_table(self) -> None:
        """Every row set, so the sum carries all sixteen terms."""
        self._check("1" * 16)

    def test_a_single_minterm(self) -> None:
        """One term, which is the fewest a non-constant table can have."""
        self._check("0000000000000001")

    def test_four_input_parity(self) -> None:
        """Eight terms and no constant subtree anywhere -- nothing folds."""
        self._check("0110100110010110")

    def test_the_all_zero_table_still_reads_every_input(self) -> None:
        """The constant needs its reads: the contract wants ``n`` of them."""
        program = boolean.algebraic_programming_language("0" * 16)
        for name in "abcd":
            assert name in program

    def test_the_name_alphabet_is_codepoint_ascending(self) -> None:
        """``_order_key`` sorts literals by name to keep reads in order.

        That only puts the reads in *input* order if the alphabet itself
        ascends, so a name appended out of sequence would silently swap
        two inputs rather than fail.
        """
        from esolangs.tools.boolean.algebraic_programming_language import _NAMES

        assert list(_NAMES) == sorted(_NAMES)
        assert len(set(_NAMES)) == len(_NAMES)
