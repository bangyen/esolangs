"""Covers :mod:`esolangs.tools.six_five`."""

import hashlib
from itertools import permutations

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import permute_truth_table
from esolangs.tools.six_five import (
    _six_five_dag_cost,
    _six_five_hoisted,
    _six_five_markers,
    _six_five_stream_ordered,
    _six_five_walk,
)
from tests.tools.boolean_runners import (
    run_six_five,
    run_six_five_from,
)


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


def _markers(program: str) -> int:
    """How many ``4`` markers a 6-5 program really has.

    Counting ``4`` characters overcounts: a ``8n`` jump whose operand is
    ``4`` contributes one, so this tokenizes the way the interpreter does.
    """
    from esolangs.interpreters.tape_based.six_five import _tokens

    return sum(1 for token in _tokens(program) if token == "4")


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

    @staticmethod
    def _dense(n: int) -> str:
        """A hash-derived table with no structure for the trees to exploit."""
        digest = hashlib.sha256(f"dense:{n}".encode()).digest()
        bits: list[str] = []
        block = 0
        while len(bits) < 2**n:
            digest = hashlib.sha256(digest + bytes([block & 255])).digest()
            bits.extend(str(byte & 1) for byte in digest)
            block += 1
        return "".join(bits[: 2**n])

    def test_a_table_whose_distinct_subtrees_overflow_takes_the_walk(self) -> None:
        """A table past the shared budget goes on the tape instead.

        Dense n == 7 has 47 distinct subtrees against 35 labels, so every
        tree-shaped emission overflows under every order -- this used to be
        the refusal witness.  The walk spends one label per *input*: the
        reads steer the pointer to the row the inputs index, so 7 labels
        carry the whole 128-row table.
        """
        dense7 = self._dense(7)
        assert _six_five_dag_cost(dense7) > 35
        program = boolean.six_five(dense7)
        assert program == _six_five_walk(dense7)
        assert _markers(program) == 7
        for combo in range(128):
            bits = [(combo >> (6 - i)) & 1 for i in range(7)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == dense7[combo], f"inputs {bits}"

    def test_dense_ten_inputs_render_and_run(self) -> None:
        """The generator clears n == 10 on a table with nothing to fold.

        Dense n == 10 renders at 10 labels and 5319 chars (all 1024 rows
        were run exhaustively once, in 12s; this samples).  The feed check
        proves the walk reads exactly ``n`` lines -- its ``B``s sit inside
        the pointer walk, so a desync would misroute as well as misread.
        """
        dense10 = self._dense(10)
        program = boolean.six_five(dense10)
        assert _markers(program) == 10
        assert len(program) == 5319
        for combo in (0, 1, 512, 1023, *range(7, 1024, 128)):
            bits = [(combo >> (9 - i)) & 1 for i in range(10)]
            feed = iter([str(b) for b in bits])
            assert run_six_five_from(program, feed) == dense10[combo], f"row {combo}"
            assert not list(feed), f"inputs {bits} left input unread"

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
        assert improved == 192  # the rest tie, keeping the old emission

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

    def test_only_four_named_orders_are_built(self) -> None:
        """Every arity builds at most four deterministic candidates."""
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.six_five")

        # The named orders deduplicate before rendering; the bound, rather
        # than timing, prevents a factorial contest from returning.
        for n, table in (
            (6, "0" * 63 + "1"),
            (8, "0" * 255 + "1"),
            (7, ("10" * 128)[:128]),
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
            assert 1 <= built <= 4, f"n={n} built {built} candidates"

    def test_retired_arithmetic_kernel_is_gone(self) -> None:
        """Retired construction helpers do not return as dispatch candidates."""
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.six_five")

        assert not hasattr(boolean, "six_five_arithmetic")
        assert module.__all__ == ["six_five"]
        assert not hasattr(module, "_SixFiveAsm")  # the assembler went too
        assert not hasattr(module, "_six_five_nav")
        assert not hasattr(module, "_six_five_node_read")
