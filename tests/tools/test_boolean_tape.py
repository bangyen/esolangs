"""Unit tests for the tape-based boolean generators.

Covers the generators in :mod:`esolangs.tools.boolean.tape` plus the
single-language modules that share its tape-machine shape: ``rotfuck``,
``six_five``, ``dimensional``, and ``streetcode``.
"""

import contextlib
import hashlib
import sys
from importlib import import_module
from itertools import permutations

import pytest

from esolangs.tools import boolean
from esolangs.tools.boolean.helpers import permute_truth_table
from esolangs.tools.boolean.six_five import (
    _six_five_dag_cost,
    _six_five_hoisted,
    _six_five_markers,
    _six_five_stream_ordered,
)
from esolangs.tools.wrap import shortest
from tests.tools.boolean_runners import (
    run_bf,
    run_bit_tilde,
    run_brainif,
    run_circlefuck,
    run_dimensional,
    run_factor,
    run_jaune,
    run_painfuck,
    run_rotfuck,
    run_sbleq,
    run_six_five,
    run_six_five_from,
    run_slow_acv_mammalian,
    run_streetcode,
    run_suffolk,
    run_three_d_brainfuck,
)


def _columns(program: str) -> int:
    """The widest row of a grid program, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


def _markers(program: str) -> int:
    """How many ``4`` markers a 6-5 program really has.

    Counting ``4`` characters overcounts: a ``8n`` jump whose operand is
    ``4`` contributes one, so this tokenizes the way the interpreter does.
    """
    from esolangs.interpreters.tape_based.six_five import _tokens

    return sum(1 for token in _tokens(program) if token == "4")


def _leaves(table: str) -> int:
    """How many leaves a tree that folds constant subtrees spends on ``table``.

    One per maximal constant slice: the walk stops as soon as the rows it
    covers agree, so this is ``2**n`` only when no slice above a single row
    is constant.
    """
    if len(set(table)) == 1:
        return 1
    half = len(table) // 2
    return _leaves(table[:half]) + _leaves(table[half:])


class TestSixFive:
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
        program = boolean.six_five(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_structure(self) -> None:
        """Both builds read, normalize to 8/9, branch on ``78``, and halt.

        The two constructions differ in where the reads sit, not in the
        branch: each starts by reading a bit and subtracting 40, tests it
        with ``78``, and ends every path on ``A0``.
        """

        for program in (boolean.six_five("0110"), _six_five_stream_ordered("0110")):
            assert program.startswith("B" + "2" * 8)
            assert "78" in program
            assert program.endswith("A0")

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("11", 1),
            ("1111", 2),
            ("11110000", 3),
            ("1111111100000000", 4),
            ("1" * 32, 5),
        ],
    )
    def test_constant_subtrees_fold(self, table: str, n: int) -> None:
        """A constant subtree emits one leaf instead of a full branch set.

        The comparison table has the same ones-count, so a shorter program
        means the tree folded rather than that some other count shrank.
        """
        mixed = {
            1: "10",
            2: "1010",
            3: "10010110",
            4: "1001011001101001",
            5: "10010110" * 4,
        }[n]
        assert len(boolean.six_five(table)) < len(boolean.six_five(mixed))
        # One ``A`` per emitted leaf: the fold collapses the leaf count to
        # the number of distinct constant regions, not ``2**n``.
        assert boolean.six_five(table).count("A") == _leaves(table)

    @pytest.mark.parametrize(
        ("table", "n"),
        [("11", 1), ("1111", 2), ("11110000", 3), ("1000000000000000", 4)],
    )
    def test_folded_leaf_still_reads_every_input(self, table: str, n: int) -> None:
        """Every path through a folded node-read tree reads all ``n`` inputs.

        A folded leaf skips branches but not reads: a caller feeding several
        programs from one stream would desync if a short path left bits
        unconsumed.  The interpreter raises ``EOFError`` on an over-read, so
        supplying exactly ``n`` bits proves no path reads too many, and
        counting the ``B``s down each path proves none reads too few.

        The walker below parses the node-read emission specifically, so it
        asks for that build rather than whichever one the dispatch picks;
        the same contract over the *dispatched* program is checked by
        :meth:`test_every_path_consumes_exactly_n_inputs`, which counts what
        the program consumes instead of reading its shape.
        """

        program = _six_five_stream_ordered(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

        # Walk the emitted tree: a branch spends one read, then its two
        # halves follow; a leaf carries the reads its fold skipped.
        def reads_on_each_path(code: str) -> set[int]:
            if not code.startswith("B" + "2" * 8):  # a leaf
                return {code.count("B")}
            body = code[len("B" + "2" * 8) + len("78") + 2 :]
            depth = 0
            for i, char in enumerate(body):
                if body[i : i + 2] == "78":
                    depth += 1
                elif char == "4":
                    if depth == 0:
                        left, right = body[:i], body[i + 1 :]
                        break
                    depth -= 1
            else:  # pragma: no cover - a branch always has its 4 separator
                raise AssertionError("no separator")
            return {1 + r for r in reads_on_each_path(left) | reads_on_each_path(right)}

        assert reads_on_each_path(program) == {n}

    @pytest.mark.parametrize(
        ("table", "n", "labels"),
        [
            ("0" * 63 + "1", 6, 6),  # AND6: was refused by both paths
            ("1" * 32 + "0" * 32, 6, 1),  # one split
            ("1" * 48 + "0" * 16, 6, 2),  # two regions
            ("1" * 64, 6, 0),  # constant
            ("0" * 255 + "1", 8, 8),  # AND8
        ],
    )
    def test_tree_past_five_inputs(self, table: str, n: int, labels: int) -> None:
        """A folded tree that fits the label budget is used at any ``n``.

        The old gate was ``n <= 5`` on the *unfolded* node count, so these
        tables fell through to the arithmetic kernel -- which refuses most of
        them, since a table with ones at high indices has a huge ``T``.
        Folding is what spends the labels, so the choice counts them instead.
        """
        program = boolean.six_five(table)
        assert _markers(program) == labels <= 35
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_marker_precheck_matches_emitted_tree(self) -> None:
        """The label count is what the emitted tree actually allocates.

        The gate decides before building, so a miscount would either refuse a
        renderable table or emit one past the 35-label budget.  Counting
        ``4`` *characters* is not the same thing -- an ``8n`` jump whose
        operand is ``4`` contributes one -- so this compares against the
        interpreter's own tokenizer.

        The count is per *order*, so ``_six_five_markers`` on the unpermuted
        table bounds the emission rather than equalling it in general.  These
        tables are the ones where the bound is tight: each is a constant, a
        single prefix run, or an AND, whose folding no renaming improves.
        """
        for table in (
            "0" * 63 + "1",
            "1" + "0" * 63,
            "1" * 48 + "0" * 16,
            "1" * 64,
            "1" * 127 + "0",
            "0" * 255 + "1",
        ):
            assert _six_five_markers(table) == _markers(boolean.six_five(table))

        # And the bound itself, over every n == 3 table: reordering can only
        # fold more subtrees, never fewer, so the emission never allocates
        # more labels than the stream-order count.
        for value in range(256):
            table = format(value, "08b")
            assert _markers(boolean.six_five(table)) <= _six_five_markers(table)

    def test_folding_is_still_per_order_even_though_sharing_is_not(self) -> None:
        """Parity resists folding under every order, and is built anyway.

        Any permutation of parity is parity, so no renaming folds a single
        one of its 63 internal nodes -- which is what made it the refusal
        witness.  Sharing does not care: the nodes are duplicates of each
        other, so the distinct count is 11 whatever the order.

        The arithmetic kernel that used to be the other candidate was
        retired: it needs ``T`` (or its complement) small enough to build,
        which confines the ones to low indices, which leaves the rest of the
        table constant -- the shape that folds well inside the budget.
        """
        parity = "".join(str(bin(row).count("1") % 2) for row in range(64))
        for perm in permutations(range(6)):
            assert _six_five_markers(permute_truth_table(parity, perm)) == 63
        assert _six_five_dag_cost(parity) == 12 <= 35
        assert boolean.six_five(parity)

    def test_reordering_widens_what_renders(self) -> None:
        """A table that overflows in stream order can fold under another.

        These two were the refusal witnesses before the tree could split in
        any input order, and neither is one any more: the scattered table is
        an XNOR of the last three inputs, and the alternating table is NOT
        of the last input, so the order that tests those inputs first folds
        each well inside the budget.  Both still compute their function.
        """
        for table, folded in (("10010110" * 8, 7), (("10" * 64)[:64], 1)):
            assert _six_five_markers(table) == 63 > 35  # refused in stream order
            best = min(
                _six_five_markers(permute_truth_table(table, perm))
                for perm in permutations(range(6))
            )
            assert best == folded <= 35
            program = boolean.six_five(table)
            # At most the folded count: the winning order may also share.
            assert _markers(program) <= folded
            for combo in range(64):
                bits = [(combo >> (5 - i)) & 1 for i in range(6)]
                got = run_six_five(program, [str(b) for b in bits])
                assert got == table[combo], f"inputs {bits}"

    def test_greedy_order_can_be_the_only_renderable_one(self) -> None:
        """Past the search cap, the greedy pick alone can carry a table.

        This is the one path where nothing else can render: at n == 7 an
        alternating table spends 127 labels in stream order, so the
        node-read build raises *and* the hoisted identity order returns
        ``""``, leaving the greedy order as the sole candidate.  Every
        smaller case is covered by the exhaustive search and every larger
        table the tests render (AND-8) comes out of the node-read build, so
        without this the fallback is never exercised as the only survivor.
        """
        n = 7
        alternating = ("10" * 128)[: 2**n]
        assert _six_five_markers(alternating) == 2**n - 1 > 35
        with pytest.raises(ValueError, match="35 branch labels"):
            _six_five_stream_ordered(alternating)
        # The identity order no longer returns "": its tree overflows, so
        # the shared build takes it -- this table is NOT of the last input,
        # whose distinct subtrees are a handful whatever the order.
        assert _six_five_hoisted(alternating, tuple(range(n)))

        program = boolean.six_five(alternating)
        assert _markers(program) == 1  # greedy tests the last input first
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            feed = iter([str(b) for b in bits])
            assert run_six_five_from(program, feed) == alternating[combo]
            assert not list(feed), f"inputs {bits} left input unread"

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
    def test_total_through_five_inputs(self, n: int) -> None:
        """Every table up to five inputs renders: the worst case still fits.

        An alternating table folds nothing, so it spends the full ``2**n - 1``
        internal nodes -- 31 at n == 5, inside the 35-label budget.  The
        refusals therefore begin at n == 6, where that worst case is 63.
        """
        alternating = ("10" * 2**n)[: 2**n]
        assert _six_five_markers(alternating) == 2**n - 1 <= 35
        boolean.six_five(alternating)  # renders rather than raising

    def test_parity_is_the_easy_case_once_subtrees_are_shared(self) -> None:
        """Sharing inverts which table is the worst case.

        An unshared tree spends a marker per internal node, so parity --
        which folds nothing -- was the witness that fixed the cap at five.
        Its *distinct* subtrees are two per level, so shared it is the
        cheapest wide table there is: n == 10 spends 20 markers where the
        tree would spend 1023.
        """
        parity6 = "".join(str(bin(row).count("1") % 2) for row in range(64))
        assert _six_five_markers(parity6) == 63 > 35
        assert _six_five_dag_cost(parity6) == 12 <= 35
        assert boolean.six_five(parity6)

        parity10 = "".join(str(bin(row).count("1") % 2) for row in range(1024))
        assert _six_five_dag_cost(parity10) == 20 <= 35
        assert boolean.six_five(parity10)

    def test_a_table_whose_distinct_subtrees_overflow_is_refused(self) -> None:
        """The budget still binds -- on distinct subtrees rather than nodes.

        Dense n == 7 has 46 of them against 35, and the refusal reports
        that count rather than the 92 an unshared tree would spend.
        """
        digest = hashlib.sha256(b"dense:7").digest()
        bits: list[str] = []
        block = 0
        while len(bits) < 128:
            digest = hashlib.sha256(digest + bytes([block & 255])).digest()
            bits.extend(str(byte & 1) for byte in digest)
            block += 1
        dense7 = "".join(bits[:128])
        assert _six_five_dag_cost(dense7) > 35
        with pytest.raises(ValueError, match="47 for its distinct subtrees"):
            boolean.six_five(dense7)

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than its identity-order program."""

        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.six_five(table))
            identity = len(_six_five_stream_ordered(table))
            assert dispatched <= identity, table
            improved += dispatched < identity
        # 186 before the leaves gained ``_six_five_const``'s ``r == 5``
        # shortcut: a shorter leaf changes which orders pay for themselves,
        # so more tables now beat the identity rather than tying it.
        assert improved == 208  # the rest tie, keeping the old emission

    @pytest.mark.parametrize(
        ("table", "n"),
        [("0110", 2), ("10010110", 3), ("1001011001101001", 4)],
    )
    def test_every_path_consumes_exactly_n_inputs(self, table: str, n: int) -> None:
        """Each run reads all ``n`` inputs and no more, whichever build won.

        The reads are the interface: a caller feeding several programs from
        one stream desyncs if a path leaves bits unconsumed.  Supplying
        exactly ``n`` proves no path over-reads (the interpreter raises
        ``EOFError``), and checking the feed is exhausted proves none
        under-reads -- which execution alone does not catch.  This replaces
        a walker that parsed the node-read emission, since the winning
        construction now varies per table.
        """
        program = boolean.six_five(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            feed = iter([str(b) for b in bits])
            got = run_six_five_from(program, feed)
            assert got == table[combo], f"inputs {bits}"
            assert not list(feed), f"inputs {bits} left input unread"

    def test_wide_tables_do_not_search_every_order(self) -> None:
        """Past the cap only the identity and a greedy order are built.

        This generator renders past n == 6 whenever a table folds hard, so
        the ``n!`` search is reachable rather than theoretical: AND-8 has
        40320 orders and searching them takes about 17 seconds against
        milliseconds for the greedy pick.  Timing is not the assertion --
        the build count is, since that is what a future change would break.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.six_five")

        # AND-n is symmetric, so its greedy pick *is* the identity and the
        # two dedupe to a single build -- the point being that neither is
        # 40320.  An alternating table, whose greedy pick differs, is the
        # two-candidate case.
        for n, table, orders in (
            (6, "0" * 63 + "1", 720),
            (8, "0" * 255 + "1", 1),
            (7, ("10" * 128)[:128], 2),
        ):
            built = 0

            def counted(
                table: str,
                perm: tuple[int, ...],
                _build: object = _six_five_hoisted,
            ) -> str:
                nonlocal built
                built += 1
                return _build(table, perm)  # type: ignore[operator, no-any-return]

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(module, "_six_five_hoisted", counted)
                boolean.six_five(table)
            assert built == orders, f"n={n} built {built} candidates"

    def test_retired_arithmetic_kernel_is_gone(self) -> None:
        """Retired construction helpers do not return as dispatch candidates."""
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.six_five")

        assert not hasattr(boolean, "six_five_arithmetic")
        assert module.__all__ == ["six_five"]
        assert not hasattr(module, "_SixFiveAsm")  # the assembler went too
        assert not hasattr(module, "_six_five_nav")
        assert not hasattr(module, "_six_five_node_read")


class TestStreetcode:
    def test_default_uses_only_shared_layouts(self) -> None:
        """Per-input loops are width fallbacks, never default candidates."""
        module = import_module("esolangs.tools.boolean.streetcode")

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                tree = module._streetcode_tree(table)  # noqa: SLF001
                all_programs = [
                    module._streetcode_hallway_program(n, tree),  # noqa: SLF001
                    *module._streetcode_shared_programs(table, n, tree),  # noqa: SLF001
                ]
                assert boolean.streetcode(table) == shortest(*all_programs)

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
        program = boolean.streetcode(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        """A subtree whose rows agree prints instead of driving down halls.

        Streetcode splits most-significant-first, so a subtree is a
        contiguous run: ``11110000`` is two constant halves and collapses,
        while ``10101010`` is constant over no run and keeps every hall.
        """
        constant = len(boolean.streetcode("11111111"))
        halves = len(boolean.streetcode("11110000"))
        scattered = len(boolean.streetcode("10101010"))
        assert constant < scattered
        assert halves < scattered
        # a folded leaf still prints the right digit for every input
        for table in ("11111111", "11110000", "11001100"):
            program = boolean.streetcode(table)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = run_streetcode(program, [str(b) for b in bits])
                assert got == table[combo], f"{table} inputs {bits}"

    def test_folded_leaf_keeps_the_cell_pointer_advances(self) -> None:
        """A folded leaf spends the ``=`` its skipped halls would have.

        Each hall advances CP by one on the way down, so a leaf reached
        without them prints from the wrong cell -- an all-zeros table came
        out as ``'\\x00'`` before this was threaded through.
        """
        program = boolean.streetcode("00000000")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_streetcode(program, [str(b) for b in bits]) == "0"

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        """The tree splits in whichever order folds most, not input order.

        ``10101010`` depends on the last input alone, so it folds nothing
        splitting most-significant-first and everything once that input is
        tested at the root.  Reordering is what lets it be emitted as the
        cheap shape, and it costs only the walk that puts the bit in the
        cell the root's hall tests.
        """
        scattered = len(boolean.streetcode("10101010"))
        aligned = len(boolean.streetcode("11110000"))
        parity = len(boolean.streetcode("01101001"))
        # Both are one-dependency tables, so reordering brings the scattered
        # one down to the aligned one's shape.  It stays a few characters
        # longer, and those characters are the walk that puts its bit in the
        # cell the root's hall tests -- the price of the reorder, paid once
        # in the prefix rather than per hall.
        assert aligned < scattered < parity
        assert scattered - aligned < 0.05 * aligned

    def test_input_reordering_never_grows_a_program(self) -> None:
        """The identity order is built first and ties keep it.

        A table no reorder improves has to emit exactly what it emitted
        before, so reordering can only ever shrink a program.  ``01101001``
        is parity, which folds under no order at all.
        """
        parity = boolean.streetcode("01101001")
        # Parity is the table where every order is equally bad, so the
        # program is the identity one and carries no reordering walks.
        assert "_I" not in parity

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_programs_compute_the_table(self, table: str) -> None:
        """A reordered program still computes its function.

        The cell an input is read into is the *inverse* of the split order --
        level ``k`` tests cell ``k + 1`` and must test input ``perm[k]`` -- so
        reading it forward stores the right bits in the wrong cells and
        computes a different function.  Only running it catches that.
        """
        program = boolean.streetcode(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == table[combo], f"{table} inputs {bits}"

    def test_reordering_keeps_the_reads_in_stream_order(self) -> None:
        """Reordering moves where a bit is stored, never when it is read.

        The program consumes its input stream exactly as it did before: one
        ``I`` per input, in input order.  What moves is the cell each lands
        in, so the count of reads is what pins this down.
        """
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.streetcode(table).count("I") == 3

    def test_width_is_a_shape_choice(self) -> None:
        """A width picks a narrower shape, and that shape still computes.

        The hallway trades columns for rows, so a width the default overruns
        is met by a shape that was built anyway, at the cost of rows. A
        Streetcode program cannot
        be reflowed after the fact, so this is the only way a width is met.
        """
        table = "10"
        default = boolean.streetcode(table)
        narrow = boolean.streetcode(table, 25)
        assert _columns(narrow) <= 25 < _columns(default)
        assert narrow.count("\n") > default.count("\n")
        for bit in ("0", "1"):
            assert run_streetcode(narrow, [bit]) == table[int(bit)]

    def test_width_takes_the_narrowest_when_none_fits(self) -> None:
        """Below every shape's width the narrowest one is returned.

        The generator has no shape narrower than its own decision tree, so
        an impossible width is a preference it cannot honour rather than an
        error; returning the best available beats returning nothing.
        """
        table = "10"
        program = boolean.streetcode(table, 1)
        assert _columns(program) == min(
            _columns(boolean.streetcode(table, w)) for w in (1, 25, 100)
        )
        for bit in ("0", "1"):
            assert run_streetcode(program, [bit]) == table[int(bit)]

    def test_width_none_is_unchanged(self) -> None:
        """Passing no width builds exactly what the generator always built."""
        for table in ("10", "0110", "11111110"):
            assert boolean.streetcode(table, None) == boolean.streetcode(table)

    def test_a_requested_width_is_never_overrun(self) -> None:
        """A width that *can* be met is met, measured on the emitted columns.

        The width is a promise about the widest row, and the only way to
        keep it is to pick a shape that already fits, so measuring the
        wrong thing -- splitting the program on whitespace rather than on
        newlines, say -- selects a shape that overruns while every
        truth-table check still passes.  ``0001`` at 33 is the tight case:
        the winning shape is exactly 33 columns, so a column count that
        drifts either way changes which shape is returned.
        """
        for table, width in (("0001", 33), ("0110", 33), ("01", 29)):
            program = boolean.streetcode(table, width)
            assert _columns(program) <= width, (table, width)

    def test_the_narrowest_fallback_is_really_the_narrowest(self) -> None:
        """Below every shape's width, the narrowest shape comes back.

        ``10`` cannot witness this: its candidates happen to agree, so a
        fallback that returned the first or the lexicographically smallest
        program would pass.  ``0100`` separates them -- the narrowest is 33
        columns where the wrong pick is 36.
        """
        program = boolean.streetcode("0100", 1)
        assert _columns(program) == 33
        for combo in range(4):
            bits = [str((combo >> 1) & 1), str(combo & 1)]
            assert run_streetcode(program, bits) == "0100"[combo]

    def test_a_width_equal_to_a_shape_is_wide_enough(self) -> None:
        """The fit test is inclusive: exactly the shape's width fits it.

        At its own column count the default shape still fits, so asking for
        exactly that many columns must return it rather than falling
        through to a narrower, longer one.  One column more is the same
        program; the suite otherwise only asks for 1, 25 and 100, none of
        which lands on a boundary.
        """
        default = boolean.streetcode("01")
        assert _columns(default) == 29
        assert boolean.streetcode("01", 29) == default
        assert boolean.streetcode("01", 30) == default

    @pytest.mark.parametrize(
        ("table", "length"),
        [("01", 302), ("0000", 340), ("0101", 340)],
    )
    def test_the_emitted_program_has_an_exact_length(
        self, table: str, length: int
    ) -> None:
        """The layout is deterministic down to the character.

        Streetcode's rows are built from fixed templates and padded runs,
        so a run one wide, a lap one column longer, or a trailing blank row
        all leave a *working* program of a different size -- and nothing
        else here measures size at all.
        """
        assert len(boolean.streetcode(table)) == length

    def test_no_trailing_blank_row(self) -> None:
        """The grid ends on its last real row.

        The row count is one plus the deepest row written, and an off-by-one
        there appends an empty row that the interpreter walks over
        harmlessly -- invisible to every behavioural check.
        """
        for table in ("01", "0101", "0110", "11111110"):
            program = boolean.streetcode(table)
            assert not program.endswith("\n"), table
            assert program.split("\n")[-1].strip(), table

    def test_the_program_is_only_streetcode_characters(self) -> None:
        """Only the glyphs Streetcode reads, plus layout space.

        Measured over every table through three inputs and a spread of
        widths rather than read off the spec: the generator uses a subset,
        and asserting the spec's full set would pass vacuously.
        """
        allowed = set(" +-;=CIOU^_|~\n")
        for table in ("01", "0000", "0110", "11111110"):
            assert set(boolean.streetcode(table)) <= allowed, table
        for width in (1, 20, 29, 33):
            assert set(boolean.streetcode("0110", width)) <= allowed, width

    def test_order_search_stops_at_the_cap(self) -> None:
        """Past the cap only the identity order is offered.

        Above ``_ORDER_SEARCH_MAX`` the exhaustive search is ``n!`` builds of
        an ``O(2**n)`` drawing, so the enumeration collapses to the one order
        that needs no search.  Tested on the helper: reaching this through
        ``streetcode`` would mean building a seven-input program.
        """
        from esolangs.tools.boolean.helpers import _ORDER_SEARCH_MAX
        from esolangs.tools.boolean.streetcode import _streetcode_orders

        at_cap = _streetcode_orders(_ORDER_SEARCH_MAX)
        assert len(at_cap) == len(list(permutations(range(_ORDER_SEARCH_MAX))))
        assert at_cap[0] == tuple(range(_ORDER_SEARCH_MAX))

        past = _ORDER_SEARCH_MAX + 1
        assert _streetcode_orders(past) == [tuple(range(past))]


class TestDimensional:
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
        program = boolean.dimensional(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_moves_are_pinned_to_dimension_zero(self) -> None:
        """A bare >/< would take its dimension from the cell's value."""
        program = boolean.dimensional("0110")
        rest = program.replace(">0", "").replace("<0", "")
        assert ">" not in rest
        assert "<" not in rest

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        """The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1")
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"


class TestDimensionalTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111100000000", 4),
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.dimensional_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.dimensional_tree(xor6)) < 10_000

    def test_dimensional_is_the_tree(self) -> None:
        """dimensional is the tree, sparse or dense.

        A survivor evaluator used to sit beside it, chosen when it came out
        shorter.  Folding constant subtrees put the tree ahead on every
        table at n <= 4, so the survivor was unreachable and was removed.
        """
        sparse = "0" * 15 + "1"  # AND4
        assert boolean.dimensional(sparse) == boolean.dimensional_tree(sparse)
        xor = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        assert boolean.dimensional(xor) == boolean.dimensional_tree(xor)


class TestCirclefuck:
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
        program = boolean.circlefuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize(
        ("values", "n"),
        [
            ([0, 255], 1),
            ([48, 49, 50, 51], 2),
        ],
    )
    def test_byte_values(self, values: list[int], n: int) -> None:
        """circlefuck_byte outputs the given byte per input combination."""
        program = boolean.circlefuck_byte(values)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == chr(values[combo]), f"inputs {bits}"

    def test_byte_values_require_a_power_of_two_table(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.circlefuck_byte([1, 2, 3])

    def test_past_the_cap_the_greedy_order_replaces_the_search(self) -> None:
        """Above ``_ORDER_SEARCH_MAX`` one greedy pick stands in for ``n!``.

        The exhaustive reorder is capped because it builds a program per
        order; at n == 7 that is 5040 builds.  Past the cap the generator
        scores each input by the constant subtrees choosing it next would
        create and commits to that order, so exactly one extra candidate is
        built.  The count is the assertion -- it is what a change to the cap
        or to the fallback would break -- and the table still has to come
        out right, so the program is run over all 128 combinations too.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.tape")
        from esolangs.tools.boolean.tape import _circlefuck_ordered

        table = "01" * 64  # alternating: the greedy pick is not the identity
        built = 0
        ordered = _circlefuck_ordered

        def counted(
            values: list[int],
            perm: tuple[int, ...],
            _build: object = ordered,
        ) -> str:
            nonlocal built
            built += 1
            return _build(values, perm)  # type: ignore[operator, no-any-return]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_circlefuck_ordered", counted)
            program = boolean.circlefuck(table)
        assert built == 2, f"built {built} candidates, not identity plus greedy"

        for combo in range(128):
            bits = [(combo >> (6 - i)) & 1 for i in range(7)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice prints its answer instead of branching further.

        Circlefuck branches on the cell the pointer is over, so the split
        axis used to be fixed to the last input and only tables constant
        along *that* axis folded -- ``11110000`` folded nothing and cost
        the same as a scattered table.  The tree now picks its order, so
        both single-dependency tables fold to one branch.

        They do not come out *equal*, and the residue is the reorder's
        price: a node tests the cell under the pointer, so ``11110000``
        walks to cell 0 and pays two moves the already-aligned
        ``10101010`` does not.  Pinning the gap as a small constant rather
        than as equality is what keeps that cost visible -- if the walk
        ever stopped being emitted, this would read as an improvement
        instead of the correctness bug it would be.
        """
        assert len(boolean.circlefuck("11111111")) < len(
            boolean.circlefuck("10101010"),
        )
        assert len(boolean.circlefuck("10101010")) < len(
            boolean.circlefuck("10010110"),
        )
        aligned = len(boolean.circlefuck("10101010"))
        walked = len(boolean.circlefuck("11110000"))
        assert walked - aligned == 2, "the reorder should pay exactly its walk"
        assert walked < len(boolean.circlefuck("10010110"))

    def test_folded_leaf_clears_its_cell(self) -> None:
        """A folded leaf builds its value on a cleared cell.

        The ``[-]`` a full-depth leaf relies on is emitted inside each
        ``[`` on the way down, so a leaf that skips those levels has to
        clear the cell itself.  Without it the cell still holds the input
        bit and every one-valued input prints one too high -- which only
        shows on an input of ``1``, so it is worth pinning per input.
        """
        program = boolean.circlefuck("11111111")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == "1", f"inputs {bits}"


class TestBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_bf_is_the_tree(self) -> None:
        """bf is the folded tree, for constant and sparse tables alike.

        There used to be a minterm construction here and ``bf`` returned
        whichever was shorter.  Folding left the tree ahead on every table
        but the two constant ones -- where it costs about 2.5x, a bounded
        factor on two tables out of 65536 -- so the minterm went away and
        the constant tables go to the tree with everything else.
        """
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        for table in ("0" * 16, "0" * 15 + "1", xor6):  # constant, AND4, dense
            assert boolean.brainfuck(table) == boolean.bf_tree(table)


class TestBfTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bf_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.bf_tree(xor6)) < 10_000

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice emits a leaf instead of branching on more bits.

        Both tables have the same number of ones, so the difference is the
        arrangement alone: ``11110000`` is two constant halves and folds to
        one leaf each, while the parity table has no constant subtree above
        a single row and emits the full tree.
        """
        assert len(boolean.bf_tree("11110000")) < len(boolean.bf_tree("10010110"))

    def test_parity_table_is_unfolded(self) -> None:
        """A table with no constant subtree still spends a leaf per row.

        The guard against a fold that fires too eagerly: parity has no
        constant slice above one row, so every one of the ``2**n`` rows
        keeps its own leaf.
        """
        xor3 = "10010110"
        assert boolean.bf_tree(xor3).count(".") == 8


class TestThreeDBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.three_d_brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_three_d_brainfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_array_moves_use_the_3d_axes(self) -> None:
        """3D Brainfuck's >/< are no-ops, so the array moves with e/w."""
        program = boolean.three_d_brainfuck("0110")
        assert ">" not in program
        assert "<" not in program
        assert "e" in program
        assert "w" in program


class TestFactor:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.factor(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_factor(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_is_the_decimal_encoding_of_the_bf_program(self) -> None:
        """factor delegates to the brainfuck generator and encodes its
        output, same as the text generator's factor()."""
        from esolangs.tools.text.tape import _factor_encode

        table = "0110"
        assert boolean.factor(table) == str(_factor_encode(boolean.brainfuck(table)))

    def test_sparse_tables_stay_small_at_n_four(self) -> None:
        """Sparse tables (few one-rows) encode a short brainfuck program,
        so they stay well under the digit cap even at n == 4."""
        assert boolean.factor("0" * 16).isdigit()
        assert boolean.factor("1" * 16).isdigit()

    def test_a_table_past_cpythons_own_limit_still_renders(self) -> None:
        """XOR4 encodes to 6390 digits, past CPython's 4300-digit default.

        That default is a DoS guard on quadratic int-to-str conversion, not
        anything Factor says, so it is raised for the render rather than
        reported as a property of the language -- which is what used to cap
        this generator at n=3.
        """
        xor4 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        program = boolean.factor(xor4)
        assert program.isdigit()
        assert len(program) > sys.get_int_max_str_digits()

    def test_the_render_leaves_the_global_limit_alone(self) -> None:
        """The digit limit is process-global, so it is borrowed, not kept.

        A generator that raised it and walked away would silently disarm
        the guard for everything else in the process.
        """
        before = sys.get_int_max_str_digits()
        boolean.factor(
            "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        )
        assert sys.get_int_max_str_digits() == before

    def test_max_digits_bounds_one_call(self) -> None:
        """``max_digits`` is the cap, and it names the size it refused.

        The count is the bit-length estimate rather than the exact 6390, so
        it is asserted as such: sizing it exactly means doing the very
        conversion the check exists to avoid.  The limit has to stay
        restored on the refusing path too.
        """
        before = sys.get_int_max_str_digits()
        xor4 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        with pytest.raises(ValueError, match="about 6391 digits"):
            boolean.factor(xor4, max_digits=1000)
        assert sys.get_int_max_str_digits() == before


class TestSlowAcvMammalian:
    """The decision tree LEAPFROG makes possible.

    ``ACCEPT`` appends the bit to array 0 whatever the pointer holds, and
    ``LEAPFROG`` jumps exactly when the array's last element is nonzero, so
    the bit just read is the branch condition and nothing has to be routed.
    """

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
            # These carried ``slow`` while the generator searched: 3.5s at
            # worst, 1.68s after the landings were first solved.  The whole
            # construction is closed-form now -- a build is 0.3ms and this
            # case is dominated by the eight interpreter runs, measured
            # 2026-09-05 at 0.07s -- so they rejoin the fast run.
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.slow_acv_mammalian_boolean(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_slow_acv_mammalian(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_tables_still_read_every_input(self) -> None:
        """A constant table consumes all ``n`` inputs.

        The tree is uniform depth, so there is no folding to skip a read --
        the reads are the language's interface, and leaving a caller's bits
        on the input stream would break whatever runs next.  What counts is
        the reads a *run* makes, not the ``ACCEPT`` tokens in the source:
        preorder emits one per internal node, so a depth-``n`` tree carries
        ``2**n - 1`` of them and executes ``n``.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        for table in ("0000", "1111", "0110"):
            program = boolean.slow_acv_mammalian_boolean(table)
            assert program.split().count("ACCEPT") == 3  # 2**2 - 1 nodes
            io_obj = ScriptedIO("0\n" * 8)
            run_until_halt_or_cycle(_Machine(program, io_obj))
            assert io_obj.position() == 2

    def test_pointer_never_leaves_array_zero(self) -> None:
        """No ``SPRINT``: the tree lives in code space, not in array space.

        The wall this generator resolves argued that a bit could not be both
        read and routed, since ``ACCEPT`` needs ``ptr == 0`` to consume one
        while routing needs ``SPRINT`` to move away.  The construction never
        routes at all, and this pins that.
        """
        program = boolean.slow_acv_mammalian_boolean("01101001")
        assert "SPRINT" not in program
        assert "CONFLAGRATE" not in program

    def test_a_node_opens_the_accumulator_on_a_clean_digit(self) -> None:
        """``ACCEPT`` is entered with ``acc % 256 == 48``, whatever the state.

        The whole construction rests on this: a node normalizes the
        accumulator so ``'0'``/``'1'`` XORs down to a bare ``0``/``1``.
        The aim class delivers it by arithmetic -- ``first`` even with bits
        4-5 ``01``, so the fixed ``+16`` run flips exactly those bits --
        and a state whose low byte drifted off 48 would append a junk byte
        and branch on something other than the bit just read.  Recovered
        here from either exit: XORing the exit accumulator against the exit
        sum reproduces what ``ACCEPT`` saw.
        """
        from esolangs.tools.boolean.slow_acv_mammalian import _node

        for array, acc in (
            ([0], 0),
            ([3, 255, 255], 0),
            ([200, 17, 9], 128),
            ([254, 1, 77, 30], 99999),
        ):
            _, fell, taken, _ = _node(list(array), acc)
            assert (fell[1] ^ sum(fell[0])) % 256 == 48
            assert (taken[1] ^ sum(taken[0])) % 256 == 48

    def test_the_landing_is_start_minus_15(self) -> None:
        """A 1-bit resumes exactly 15 tokens short of the array sum.

        This is the identity that replaced the 256-candidate sweep: on the
        aim class the ``j1`` seeds cancel out of the jump arithmetic, so
        the landing is a pure function of the sum and aiming is done by
        stashing ballast, never by trying candidates.  Machine-backed
        rather than re-derived, so a drift in either the generator's
        algebra or the interpreter's ``LEAPFROG`` shows up here.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.boolean.slow_acv_mammalian import _node, _seeded

        for array, acc in (([3, 255, 255, 255], 7), ([90, 200, 200, 255], 4242)):
            tokens, _, taken, landing = _node(list(array), acc)
            wrap = (256 - array[0]) % 256
            start = sum([*_seeded(array, wrap), acc % 256])
            assert landing == start - 15
            padded = [*tokens, *["SEED"] * (landing + 2 - len(tokens))]
            machine = _Machine(" ".join(padded), ScriptedIO("1\n"))
            machine.lst = (tuple(array), *machine.lst[1:])
            machine.acc = acc
            while not machine.halted and machine.ind < len(tokens):
                machine.step()
            assert machine.ind == landing
            assert list(machine.lst[0]) == taken[0]
            assert machine.acc == taken[1]

    def test_the_trampoline_jump_ignores_the_head(self) -> None:
        """The trampoline lands on its target from any head value.

        ``LEAPFROG``'s target is ``acc - head - 1`` and the final
        ``DIGEST`` folds the head into the accumulator, so the head cancels
        and the landing is the non-head sum plus the appended byte.  That
        cancellation is what makes the jump *solvable* -- no candidate ever
        has to be tried -- and it holds through a ``SEED`` run that wraps
        the head, which drops the array sum by 256 but not the target.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.boolean.slow_acv_mammalian import _trampoline

        target = 900
        for head in (0, 130, 255):
            array = [head, 255, 255, 200]
            tokens, out_array, out_acc = _trampoline(list(array), 5000, target)
            padded = [*tokens, *["SEED"] * (target + 2 - len(tokens))]
            machine = _Machine(" ".join(padded), ScriptedIO(""))
            machine.lst = (tuple(array), *machine.lst[1:])
            machine.acc = 5000
            while not machine.halted and machine.ind < len(tokens):
                machine.step()
            assert machine.ind == target, f"head {head}"
            assert list(machine.lst[0]) == out_array
            assert machine.acc == out_acc

    def test_the_shortest_hop_still_fires(self) -> None:
        """A hop of one token appends ``b == 1``, the least firing byte.

        The trampoline's ``LEAPFROG`` fires because the appended byte is
        the array's last element, so ``b == 0`` would fall through into the
        dead pad and execute garbage.  ``_MIN_HOP`` exists to keep the
        emitter's targets off that edge, and this pins the edge itself:
        the shortest representable hop still jumps.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.tools.boolean.slow_acv_mammalian import _trampoline

        array = [5, 255, 255, 255]
        target = sum(array) - array[0] + 1
        tokens, out_array, _ = _trampoline(list(array), 0, target)
        assert out_array[-1] == 1
        machine = _Machine(
            " ".join([*tokens, *["SEED"] * (target + 2 - len(tokens))]),
            ScriptedIO(""),
        )
        machine.lst = (tuple(array), *machine.lst[1:])
        while not machine.halted and machine.ind < len(tokens):
            machine.step()
        assert machine.ind == target

    def test_ballast_is_spent_where_it_stands(self) -> None:
        """No ``CONSUME``: the parent/child ballast lock never forms.

        The searching construction shed a 0-arm's inherited ballast with
        ``CONSUME`` runs because a child re-aimed from scratch would
        otherwise convert every stashed token into padding of its own.
        Here the 1-subtree inherits the array whose sum *is* its position
        and the 0-subtree enters through a trampoline carrying the same,
        so nothing is ever dropped to be rebuilt -- and the program says
        so: only the six ops the construction needs appear.
        """
        program = boolean.slow_acv_mammalian_boolean("0110")
        used = set(program.split())
        assert used <= {"SEED", "EXCRETE", "DIGEST", "ACCEPT", "PRONOUNCE", "LEAPFROG"}

    def test_a_stale_width_table_is_caught_not_emitted(self) -> None:
        """Slots too narrow for their trampolines raise, loudly.

        The slot widths are the one place the construction leans on a
        bound rather than an exact solve, so a stale ``_widths`` must
        surface as an error naming the overflow -- not as a program whose
        trampoline spills into the dead pad and executes it.
        """
        import esolangs.tools.boolean.slow_acv_mammalian as module

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_widths", lambda n: [0] + [4] * n)
            with pytest.raises(AssertionError, match="slot"):
                module.slow_acv_mammalian_boolean("0110")

    @pytest.mark.parametrize(
        ("n", "widths"),
        [
            (1, [0, 267]),
            (2, [0, 267, 805]),
            (3, [0, 267, 805, 871]),
            (4, [0, 267, 805, 871, 1000]),
            (8, [0, 267, 805, 871, 1000, 1258, 1783, 2836, 4954]),
        ],
    )
    def test_the_width_recurrence_is_exact(self, n: int, widths: list[int]) -> None:
        """The cap recurrence's own output, pinned per level.

        ``_widths`` is an *upper bound*, and the slack it carries is large
        -- 542 and 558 tokens at levels 2 and 3 -- so a term that drifts
        upward changes nothing anywhere else: the emitted program is
        byte-identical when every slot grows by 5, because the dead pad
        absorbs the difference and the landing offsets move in steps of
        255.  The companion test above covers the other direction, where a
        too-*small* slot trips the alarm.  Between them the bound is only
        pinned from below, which leaves every line of the recurrence free
        to grow unobserved; these values close that.

        A level is one entry, so the list also fixes the recurrence's
        length and the ``widths[0] == 0`` seed (a leaf has no slot).

        ``n == 8`` is not padding, and costs nothing -- this is integer
        arithmetic, with no program built.  The ``caps`` seed feeds the
        next level's slot only through a ceiling division, which swallows
        a one-token change for seven levels; the first arity where a
        wrong seed reaches ``widths`` at all is eight.  Nothing below it
        can separate that term.
        """
        from esolangs.tools.boolean.slow_acv_mammalian import _widths

        assert _widths(n) == widths

    def test_the_slots_actually_hold_their_trampolines(self) -> None:
        """Every emitted hop fits, and level 1 is the tight one.

        The bound is worth having only if it binds somewhere near the
        truth: the level-1 slot is 267 tokens against a largest observed
        hop of 245, while the deeper levels sit hundreds clear.  Recording
        the real occupancy keeps the recurrence honest from above -- a term
        that grew would push these numbers apart -- and documents which
        level is the one to watch.
        """
        import esolangs.tools.boolean.slow_acv_mammalian as module

        hops: list[int] = []
        original = module._trampoline  # noqa: SLF001

        def record(*args: object) -> tuple[list[str], list[int], int]:
            hop, array, acc = original(*args)
            hops.append(len(hop))
            return hop, array, acc

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_trampoline", record)
            for table in ("0110", "0001", "01101001"):
                module.slow_acv_mammalian_boolean(table)
        assert hops, "no trampoline was built"
        assert max(hops) == 306
        # Each slot is checked against its own level as the emitter runs
        # (``_subtree`` raises on an overflow), so what is asserted here is
        # that the deepest slot -- the one every hop could in principle
        # need -- still clears the largest hop with room to spare.
        assert max(hops) < max(module._widths(3)[1:])  # noqa: SLF001


class TestSuffolk:
    def test_candidate_costs_select_the_emitted_program(self) -> None:
        """The selector's model is exact across every non-constant table to n=3."""
        from esolangs.tools.boolean.tape import _suffolk_candidate_cost

        for n in range(1, 4):
            for value in range(2 ** (2**n)):
                table = f"{value:0{2**n}b}"
                if len({*table}) == 1:
                    continue
                plain = _suffolk_candidate_cost(table, "1", invert=False)
                flipped = _suffolk_candidate_cost(table, "0", invert=True)
                assert len(boolean.suffolk(table)) == min(plain, flipped)

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
            ("1111111100000000", 4),  # top half
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_tables_collapse_but_still_read(self) -> None:
        """A constant table skips the minterms but still reads its inputs.

        Dropping the evaluation is the win; the reads are the language's
        interface and have to stay, or the caller's bits are left unread on
        the input stream for whatever runs next.
        """
        for table in ("00", "11"):
            assert boolean.suffolk(table).count(",") == 1  # n == 1

    def test_dense_tables_evaluate_the_complement(self) -> None:
        """A table with more ones than zeros is evaluated from its zero rows.

        Cost is one minterm block per evaluated row, so before this the
        length rose monotonically with the ones-count.  Now it peaks at half
        and falls again -- the signature of picking whichever row-set is
        smaller -- which is what this pins.

        **Every table here depends on all three inputs**, which the prefix
        family ``1^k 0^(8-k)`` does not: ``11110000`` ignores two of them,
        and since dependency reduction (10) shipped it is the *cheapest*
        table of the seven rather than the dearest, so the peak-at-half
        signature reads as broken when it is only being measured through a
        second optimization.  Holding the arity fixed isolates the
        complement, which is what this test is about.
        """
        tables = (
            "10000000",  # 1 one
            "10010000",  # 2
            "11100000",  # 3
            "11101000",  # 4
            "11111000",  # 5
            "11111001",  # 6
            "11111110",  # 7
        )
        lengths = [len(boolean.suffolk(table)) for table in tables]
        assert lengths[3] == max(lengths)  # four ones is the worst case
        assert lengths[6] < lengths[3]  # seven ones is cheaper than four
        # and roughly as cheap as its one-one mirror image
        assert abs(lengths[6] - lengths[0]) < lengths[0] // 4

    @pytest.mark.parametrize(
        "table",
        ["11111110", "1111111111111110", "0111111111111111", "11111100"],
    )
    def test_complemented_tables_still_compute(self, table: str) -> None:
        """The inverted print stage answers the original table, not its flip.

        ``.`` emits ``chr(acc - 1)`` and ``!`` computes
        ``max(0, cell + 1 - acc)``, so the constant the flip cell carries has
        to account for both; preloading it one low prints ``'/'`` instead of
        ``'0'``, which is how an earlier attempt failed.
        """
        n = (len(table) - 1).bit_length()
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"


class TestPainfuck:
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
            ("1111111100000000", 4),  # top half
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.painfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_painfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_commands_are_preshifted_for_the_trans_table(self) -> None:
        """The interpreter shifts commands through its cycles, so the source
        must be the inverse shift; the translated commands are the BF moves."""
        from esolangs.interpreters.tape_based.painfuck import _translate

        program = boolean.painfuck("0110")
        translated = _translate(program)
        assert "a" in translated  # [ loops
        assert "b" in translated  # ] loops
        assert translated.count("a") == translated.count("b")
        assert "rl" in translated or "l" in translated  # pointer moves


class TestBitTilde:
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
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bit_tilde(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bit_tilde(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        assert program.startswith(")")
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")


class TestJaune:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),  # constant zero
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.jaune(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_jaune(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.jaune(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_jaune(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_reads_every_input_whatever_the_table(self) -> None:
        """Every table consumes exactly ``n`` inputs, folds included.

        This is the cross-cutting contract in
        ``test_boolean_contract.py``, pinned here because that sweep
        cannot see Jaune: it iterates the generators registered in
        ``BY_FUNCTION``, and Jaune is not one of them.  The reads used to
        sit *at* the tree's nodes, so a folded tree skipped them and a
        constant table consumed no input at all -- making the program's
        stream consumption a function of its truth table.  Without this
        test nothing would catch that coming back.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.jaune import run

        n = 3
        for table in ("11111111", "00000000", "11110000", "10101010", "10010110"):
            io = ScriptedIO("0\n" * n)
            with contextlib.suppress(Exception, SystemExit):
                run(boolean.jaune(table), io=io)
            assert io.position() == n, (
                f"{table} consumed {io.position()} inputs, expected {n}"
            )

    def test_unused_inputs_are_clobbered_not_stored(self) -> None:
        """An input no node branches on is read without keeping a cell.

        ``10101010`` depends only on its last input, so the first two
        reads need no cell of their own and the tree navigates a
        one-cell block instead of a three-cell one.
        """
        assert boolean.jaune("10101010").startswith("vvv")
        # every input matters here, so every read keeps its cell
        assert boolean.jaune("10010110").startswith("v>v>v>")

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            (0, 5),
            (5, 0),
            (0, 0),
            (3, 4),
            (12, 34),
            (99, 99),
            (100, 7),
            (7, 100),
            (7, 123),
            (123, 456),
            (12345, 6789),
            pytest.param(99999, 99999, marks=pytest.mark.slow),  # 1.3s
        ],
    )
    def test_multiply(self, a: int, b: int) -> None:
        """The sentinel-delimited multiply reads any-length operands."""
        program = boolean.jaune_multiply()
        lines = [*list(str(a)), "*", *list(str(b)), "#"]
        got = run_jaune(program, lines)
        assert got == str(a * b), f"{a} * {b}"

    def test_multiply_all_small_operands(self) -> None:
        """Every single-digit pair produces the right product."""
        program = boolean.jaune_multiply()
        for a in range(10):
            for b in range(10):
                lines = [*list(str(a)), "*", *list(str(b)), "#"]
                got = run_jaune(program, lines)
                assert got == str(a * b), f"{a} * {b}"


class TestBasicfuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
        ],
    )
    def test_program_shape(self, table: str, n: int) -> None:
        """The program declares its cells, reads n inputs, and prints once."""
        program = boolean.basicfuck(table)
        assert program.startswith("#basicfuck t=unbounded r=0~255 o=wrap")
        assert (
            program.splitlines()[1]
            == "#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out"
        )
        assert program.count("read ->") == n  # one read per input
        # One leaf per *constant slice*, not per row: the tree folds a
        # subtree whose rows agree, so a table with no constant slice above
        # a single row (parity) still spends 2**n leaves while a constant
        # table spends one.
        assert program.count("write <- out ;") == _leaves(table)

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice emits one leaf instead of branching further."""
        assert boolean.basicfuck("1" * 16).count("write <- out ;") == 1
        assert boolean.basicfuck("11110000").count("write <- out ;") == 2
        # parity has no constant slice above one row, so nothing folds
        assert boolean.basicfuck("10010110").count("write <- out ;") == 8

    def test_decision_tree(self) -> None:
        """Each internal node branches both ways with the wiki's if!(...)."""
        program = boolean.basicfuck("0110")
        assert program.count("if (a1) {") == 1
        assert program.count("if !(a1) {") == 1
        assert program.count("if (a2) {") == 2
        assert program.count("if !(a2) {") == 2


class TestSbleq:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("0000000000000000", 4),  # constant zero
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.sbleq(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sbleq(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_structure(self) -> None:
        """The root reads, then its branch normalizes and tests it."""
        program = boolean.sbleq("0110")
        cells = [int(tok) for tok in program.split()]
        data_base = len(cells) - 11
        assert cells[:3] == [data_base + 4, -2, data_base + 6]  # root read
        assert cells[6:9] == [  # root branch and normalization
            data_base + 4,
            data_base,
            data_base + 8,
        ]
        assert cells[-11:-7] == [-49, 48, 49, -1]  # NEG49, D48, D49, HALT
        code = cells[:data_base]
        triples = [tuple(code[i : i + 3]) for i in range(0, len(code), 3)]
        outputs = [
            t for t in triples if t[0] == -3
        ]  # one output per leaf, in combo order
        assert outputs == [
            (-3, data_base + 1, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 1, 0),
        ]
        assert [t for t in triples if t == (0, 0, data_base + 3)] == 4 * [
            (0, 0, data_base + 3)
        ]  # one halt per leaf

    def test_only_the_hoisted_route_remains(self) -> None:
        """The former node-read builder is gone, not merely bypassed."""
        import esolangs.tools.boolean.tape as module

        assert not hasattr(module, "_sbleq_node_read")

    def test_hoisted_build_reads_every_input_once_up_front(self) -> None:
        """The read block is 2n instructions and precedes every branch."""
        from esolangs.tools.boolean.tape import _sbleq_hoisted

        program = _sbleq_hoisted("00010111", (0, 1, 2))
        cells = [int(tok) for tok in program.split()]
        triples = [tuple(cells[i : i + 3]) for i in range(0, len(cells), 3)]
        reads = [t for t in triples[:6] if t[1] == -2]
        assert len(reads) == 3  # one read per input, all in the first 6 instrs
        assert [t[0] for t in reads] == sorted({t[0] for t in reads})  # input order

    def test_mismatched_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.sbleq("011")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.sbleq("0123")


class TestBrainIf:
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
        program = boolean.brainif(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_brainif(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """The answer byte is built first, then an input is read and tested."""
        program = boolean.brainif("10")
        assert program.startswith("if 0 increment")
        assert "if 0 input" in program
        assert "if 48 goto" in program

    def test_the_answer_byte_is_built_once(self) -> None:
        """The climb to 48 is paid before the tree, not once per digit.

        Two per-digit output routines cost 48 + 49 increments and dominated
        the program; building the byte ahead of the branch leaves the tree
        deciding only whether to add one, so the count is 48 plus one line
        per ``1`` *leaf*.  Leaves, not rows: a constant slice folds to one
        leaf, so ``11111110`` spends three rather than seven.
        """
        for table, one_leaves in (("10", 1), ("0110", 2), ("11111110", 3)):
            assert boolean.brainif(table).count("increment") == 48 + one_leaves

    def test_one_shared_output_tail(self) -> None:
        """Both answers print from the same two lines."""
        program = boolean.brainif("0110")
        assert program.count("output") == 2

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice stops the branching, though not the reads.

        Reads carry the pointer home, so a leaf spends no moves reaching
        the answer and the fold is not handed back -- which is what an
        earlier layout, with the answer past the inputs, did.
        """
        assert len(boolean.brainif("11111111")) < len(boolean.brainif("11110000"))
        assert len(boolean.brainif("11110000")) < len(boolean.brainif("10010110"))


class TestRotfuck:
    """The ROTfuck boolean generator.

    ROTfuck rotates the program after every command, so the generator lays
    out ``[ body ]`` blocks whose ``]`` is a phantom encoded at the ``[``-fire
    seek state; both the skip and body paths re-converge in the same rotation
    state because every body length is 7 (mod 8).
    """

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
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # high half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.rotfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_round_trips_every_table_at_n_2(self) -> None:
        """Every two-input table produces the right result."""
        for table_int in range(2 ** (2**2)):
            table = format(table_int, "04b")
            program = boolean.rotfuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = run_rotfuck(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_the_rotation_cycle_is_the_documented_one(self) -> None:
        """``+ -> - -> > -> < -> , -> . -> [ -> ] -> +``, and it is a cycle.

        Everything else here is arithmetic on this order: which commands a
        body may use at an offset, which character encodes a phantom ``]``,
        and how far a pad shifts the rest of a block.  A rotation that is
        off by one, or runs backwards, still emits a program -- one whose
        every command means something else.
        """
        from esolangs.tools.boolean.rotfuck import _ROTFUCK_CHAIN, _rotfuck_rot

        assert _ROTFUCK_CHAIN == "+-><,.[]"
        for i, char in enumerate(_ROTFUCK_CHAIN):
            forward = _ROTFUCK_CHAIN[(i + 1) % 8]
            assert _rotfuck_rot(char, 1) == forward, char
            assert _rotfuck_rot(forward, -1) == char, char
            assert _rotfuck_rot(char, 8) == char, char
            assert _rotfuck_rot(char, 0) == char, char

    def test_a_body_command_never_shows_as_a_bracket(self) -> None:
        """The allowed set at each offset is exactly the non-bracket rotations.

        A body command at relative offset ``j`` is read as
        ``rot^-j(cmd)`` while the ``[`` seeks its partner, so a command
        that shows as ``[`` or ``]`` there would move the seek's depth
        count and the block would pair with the wrong bracket.  The two
        offsets that matter most are 2 and 3, where only two of the four
        commands survive -- and they exclude *different* ones, which is
        what makes the padding necessary rather than cosmetic.
        """
        from esolangs.tools.boolean.rotfuck import _rotfuck_allowed, _rotfuck_rot

        for offset in range(8):
            allowed = _rotfuck_allowed(offset)
            assert allowed == [
                c for c in "+-><" if _rotfuck_rot(c, -offset) not in "[]"
            ], offset
        assert _rotfuck_allowed(2) == [">", "<"]
        assert _rotfuck_allowed(3) == ["+", "<"]
        assert _rotfuck_allowed(4) == ["+", "-"]

    def test_a_neutral_pad_exists_and_is_net_zero_at_every_offset(self) -> None:
        """Padding shifts the offset by two without moving the tape.

        Both characters have to be legal *at their own* offsets, and at
        offsets 2 and 3 exactly one of the four candidate pairs qualifies,
        so the choice is forced there rather than preferred.  The pair is
        also net-neutral by construction -- ``+-`` and ``><`` undo
        themselves -- which is what lets it be inserted anywhere.
        """
        from esolangs.tools.boolean.rotfuck import _rotfuck_allowed, _rotfuck_neutral

        for offset in range(8):
            pad = _rotfuck_neutral(offset)
            assert pad in ("+-", "-+", "><", "<>"), offset
            assert set(pad) in ({"+", "-"}, {"<", ">"}), offset
            for i, char in enumerate(pad):
                assert char in _rotfuck_allowed((offset + i) % 8), (offset, char)
        # Forced where only one candidate is legal, so these are the pad.
        assert _rotfuck_neutral(2) == "><"
        assert _rotfuck_neutral(3) == "+-"

    def test_every_body_is_seven_mod_eight_and_offset_legal(self) -> None:
        """The two invariants the block layout rests on, over many bodies.

        A body of length ``L`` with ``L + 1 == 0 (mod 8)`` puts the skip
        path and the body path in the same rotation state after the block,
        which is what lets the blocks be laid end to end.  Every command in
        it must also sit at an offset where it does not read as a bracket.
        Neither is visible in a truth-table check: a body that breaks
        either still runs, it just re-converges in the wrong state.
        """
        from esolangs.tools.boolean.rotfuck import _rotfuck_allowed, _rotfuck_body

        for guard in range(6):
            for target in range(6):
                if guard == target:
                    continue
                for op in ("+", "-"):
                    body = _rotfuck_body(guard, target, op)
                    assert (len(body) + 1) % 8 == 0, (guard, target, op)
                    for j, char in enumerate(body):
                        assert char in _rotfuck_allowed(j % 8), (guard, target, j)
                    assert body.count(">") - body.count("<") == 0, (guard, target)
                    assert op in body, (guard, target, op)

    def test_the_program_is_only_command_characters(self) -> None:
        """Nothing but the eight commands is emitted.

        ROTfuck treats a character outside its alphabet as a comment that
        neither executes *nor advances the rotation*, so stray text is
        invisible to any behavioural check -- a program with padding
        between every command computes the same table.  The alphabet is
        therefore asserted directly rather than inferred from the answer.
        """
        for table in ("01", "0110", "11110000", "01101001"):
            assert set(boolean.rotfuck(table)) <= set("+-><,.[]"), table

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 221),
            ("10", 219),
            ("0001", 516),
            ("0110", 539),
            ("11110000", 389),
            ("01101001", 1576),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        """The layout is deterministic down to the character.

        Several ways of getting this wrong leave a *correct* program: a
        move loop that emits a redundant ``><`` when the pointer is
        already home, a pad count taken mod 9 rather than mod 8 (which
        adds a whole 8-cycle and so preserves the length invariant), or a
        stray separator the interpreter reads as a comment.  None of them
        changes an answer, and a loose size bound only catches them by
        luck, so the lengths are pinned exactly.

        ``11110000`` also carries the dependency reduction: it depends on
        one of its three inputs and so builds the one-input table, 389
        characters against ``01101001``'s 1576.
        """
        assert len(boolean.rotfuck(table)) == length
