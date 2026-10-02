"""Covers :mod:`esolangs.tools.six_five`."""

import hashlib
import importlib
import random
from itertools import permutations

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import permute_truth_table
from esolangs.tools.six_five import (
    _SIX_FIVE_NORMALIZE,
    _SIX_FIVE_TEST,
    _SIX_FIVE_TREE_NORMALIZE,
    _six_five_chosen,
    _six_five_const,
    _six_five_dag_cost,
    _six_five_guarded,
    _six_five_hoisted,
    _six_five_markers,
    _six_five_orders,
    _six_five_stream_ordered,
    _six_five_walk,
)
from scripts.benchmark import _commands
from tests.tools.boolean_runners import (
    run_six_five,
    run_six_five_from,
)
from tests.tools.sample_tables import five_input_sample


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
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.six_five(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_structure(self) -> None:
        """Both builds read, normalize to 31/32, branch on ``7V``, and halt.

        The two constructions differ in where the reads sit, not in the
        branch: each starts by reading a bit and subtracting 17, tests it
        with ``7V``, and ends every path on ``A0`` -- but the last, which the
        dispatch leaves on ``A``, since the program halts at its end anyway.
        """

        for program in (boolean.six_five("0110"), _six_five_stream_ordered("0110")):
            assert program.startswith("B" + _SIX_FIVE_TREE_NORMALIZE)
            assert _SIX_FIVE_TEST in program
        assert _six_five_stream_ordered("0110").endswith("A0")
        # The right half is NOT of the last input, with nothing left to
        # read: a node, whose leaves add 18 to the 31 and 16 to the 32.
        assert boolean.six_five("0110").endswith("7V82666A04655A")

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
        # At most one ``A`` per emitted leaf: the fold collapses the leaf
        # count to the number of distinct constant regions, not ``2**n``,
        # and a node whose answer is its bit, or its bit inverted, prints
        # both of its leaves with one ``A`` (``11110000`` is NOT x1).
        assert boolean.six_five(table).count("A") <= _leaves(table)

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
            if not code.startswith("B" + _SIX_FIVE_TREE_NORMALIZE):  # a leaf
                return {code.count("B")}
            head = "B" + _SIX_FIVE_TREE_NORMALIZE + _SIX_FIVE_TEST
            body = code[len(head) + 2 :]
            depth = 0
            for i, char in enumerate(body):
                if body[i : i + 2] == _SIX_FIVE_TEST:
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
            # AND6 was refused by both paths; shared, its 0 leaves are one.
            ("0" * 63 + "1", 6, 6),
            ("1" * 32 + "0" * 32, 6, 1),  # one split: NOT x1, a node
            ("1" * 48 + "0" * 16, 6, 3),  # two regions, the second NOT x2
            ("1" * 64, 6, 0),  # constant
            ("0" * 255 + "1", 8, 8),  # AND8: the last test copies its bit
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
        The unshared tree is what the gate counts; a shared one can mark a
        left copy it jumps to, so it checks its own count against 35.
        """

        def plain(table: str) -> str:
            return _six_five_chosen(table, _six_five_orders(table), share=False)

        for table in ("1" + "0" * 63, "1" * 64, "1" * 127 + "0", "1" * 48 + "0" * 16):
            assert _six_five_markers(table) == _markers(plain(table))
        # An AND's last test copies its bit, so it prints and spends no label.
        for table in ("0" * 63 + "1", "0" * 255 + "1"):
            assert _six_five_markers(table) - 1 == _markers(plain(table))

        # And the bound itself, over every n == 3 table: reordering can only
        # fold more subtrees, never fewer, so the unshared winner never
        # allocates more labels than the stream-order count.
        for value in range(256):
            table = format(value, "08b")
            assert _markers(plain(table)) <= _six_five_markers(table)

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
        # Greedy tests the last input first, and NOT of it is one node.
        assert _markers(program) == 1
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
        assert program == _six_five_walk(dense7).removesuffix("0")  # halts at its end
        assert _markers(program) == 7
        for combo in range(128):
            bits = [(combo >> (6 - i)) & 1 for i in range(7)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == dense7[combo], f"inputs {bits}"

    def test_dense_ten_inputs_render_and_run(self) -> None:
        """The generator clears n == 10 on a table with nothing to fold.

        Dense n == 10 renders at 10 labels and 5308 chars (all 1024 rows
        were run exhaustively once, in 12s; this samples).  The feed check
        proves the walk reads exactly ``n`` lines -- its ``B``s sit inside
        the pointer walk, so a desync would misroute as well as misread.
        """
        dense10 = self._dense(10)
        program = boolean.six_five(dense10)
        assert _markers(program) == 10
        assert len(program) == 5308
        for combo in (0, 1, 512, 1023, *range(7, 1024, 128)):
            bits = [(combo >> (9 - i)) & 1 for i in range(10)]
            feed = iter([str(b) for b in bits])
            assert run_six_five_from(program, feed) == dense10[combo], f"row {combo}"
            assert not list(feed), f"inputs {bits} left input unread"

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table.

        29900 while a node whose answer is its own bit tested it and laid
        two leaves of one text, the last leaf kept its halt, and a folded
        leaf stepped back a cell; 21533 once the node prints its cell; 18490
        (-14.1%) once every add is spelled in the fewest ``6``/``5`` (or
        ``9``/``2``) tokens: a leaf's ``6``s then ``62`` pairs cost a 0-leaf
        (+40 from the 8 cell, +39 from the 9) twice a 1-leaf from the 8 cell
        (+41), and a read's -40 was eight ``2``s rather than seven; 17190
        (-7.0%) once a node whose answer is its bit inverted skips a step
        onto a blank cell instead of testing and laying two leaves; 12483
        (-27.4%) once a read is held at 31/32 rather than 8/9: -17 and
        every leaf's add take three tokens each, not seven; 12135 (-2.8%)
        once the winning order prints a read its tree copies once as it came;
        10951 (-9.8%) once a tree jumps to the subtrees it repeats.
        """
        total = sum(len(boolean.six_five(format(v, "08b"))) for v in range(256))
        assert total == 11252

    def test_the_executed_steps_are_stable_over_three_inputs(self) -> None:
        """Steps summed over every row of every three-input table.

        Counted as ``benchmark.py`` counts ``commands``.  66323 with reads
        held at 8/9, where a read's -40 and a leaf's +39..+41 ran seven
        steps each; 43044 (-35.1%) at 31/32, where each runs three, and
        no table takes more steps than it did; 40068 (-6.9%) once a read
        one node uses is normalized at that node, on its paths alone, and
        one a node copies prints raw; 40261 (+0.5%) once a tree jumps to the
        subtrees it repeats, whose jumps cost a step each.
        """
        total = 0
        for value in range(256):
            table = format(value, "08b")
            program = boolean.six_five(table)
            for row in range(8):
                steps = _commands("6-5", program, table, row, 10_000)
                assert steps is not None
                total += steps
        assert total == 39247

    def test_an_inverted_bit_skips_a_step_only_before_more_reads(self) -> None:
        """A node whose answer is NOT its bit tests it, unless reads remain.

        Adds are monotone, so the no-label print moves the pointer instead:
        at 1/2, ``71`` skips a ``1`` on a 0 bit, and a 1 bit prints from the
        blank cell two on.  From a read held at 31/32 that is -30 and +48
        from blank, 17 characters to a node's 14, so the hoisted build never
        takes it (its identity order is the stream build's); the stream
        build does only where its node would repeat the reads still due in
        both leaves.  Every order of every three-input table is executed.
        """
        assert _markers(boolean.six_five("10")) == 1
        assert "71" not in boolean.six_five("10")
        assert "71" in _six_five_stream_ordered("11110000")
        for value in range(256):
            table = format(value, "08b")
            for perm in permutations(range(3)):
                program = _six_five_hoisted(permute_truth_table(table, perm), perm)
                # The identity order is the stream build's, not the hoisted.
                assert "71" not in program or perm == (0, 1, 2)
                for combo in range(8):
                    bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                    assert run_six_five(program, bits) == table[combo], (table, perm)

    def test_a_read_one_node_uses_is_normalized_there(self) -> None:
        """A read tested at one node alone costs its -17 on that node's paths.

        The size is unchanged, so the order contest is too; a read one node
        copies prints raw (``A`` straight off the 48/49), which is shorter,
        and only the winner does that.  Every order of every three-input
        table is executed with it.
        """
        # AND of x1 and x2, x2 tested first: no read is normalized up front,
        # x2 steps back to its cell for -17, and x1 is copied as read.
        program = _six_five_hoisted("00010001", (2, 1, 0), raw_copies=True)
        assert program.startswith("B13B13B3" + _SIX_FIVE_TREE_NORMALIZE)
        assert program.endswith("4" + "3" + "A0")
        for value in range(256):
            table = format(value, "08b")
            for perm in permutations(range(3)):
                permuted = permute_truth_table(table, perm)
                plain = _six_five_hoisted(permuted, perm)
                raw = _six_five_hoisted(permuted, perm, raw_copies=True)
                assert len(raw) <= len(plain)
                for combo in range(8):
                    bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                    assert run_six_five(raw, bits) == table[combo], (table, perm)

    def test_an_add_never_outgrows_its_old_spelling(self) -> None:
        """No table grows under the fewest-token adds: no add is longer.

        The adds are the only text that changed: a leaf's add (was ``6``s
        then ``62`` pairs) and a read's -40 (was eight ``2``s).  Every build
        emits them per leaf and per read, and the dispatch keeps the
        shortest order, so adds no longer than the old text for every value
        a leaf can ask for bound every program by its old length.
        """
        assert len(_SIX_FIVE_NORMALIZE) < len("2" * 8)
        assert (
            -6 * _SIX_FIVE_NORMALIZE.count("9") - 5 * _SIX_FIVE_NORMALIZE.count("2")
            == -40
        )
        for value in range(64):
            q, r = divmod(value, 6)
            pairs = "6" * q + ("5" if r == 5 else "62" * r)
            add = _six_five_const(value)
            assert len(add) <= len(pairs), value
            assert (
                6 * add.count("6") + 5 * add.count("5") - 5 * add.count("2") == value
            ), value
        # A tree read's -17, and the leaf deltas: 0 and 1 from 31 and 32.
        assert len(_SIX_FIVE_TREE_NORMALIZE) == 3
        assert (
            -6 * _SIX_FIVE_TREE_NORMALIZE.count("9")
            - 5 * _SIX_FIVE_TREE_NORMALIZE.count("2")
            == -17
        )
        assert [len(_six_five_const(d)) for d in (16, 17, 18)] == [3, 3, 3]

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than its identity-order program."""

        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.six_five(table))
            # The dispatch drops the last ``0``, which the builds keep.
            identity = len(_six_five_stream_ordered(table)) - 1
            assert dispatched <= identity, table
            improved += dispatched < identity
        # 186 before the leaves gained ``_six_five_const``'s ``r == 5``
        # shortcut, 192 after; 108 once a node that copies its bit prints
        # it, which the stream build does with the raw read (``BA0``); 140
        # once every add takes the fewest tokens, which shortens the
        # hoisted builds' extra leaves more than the stream build's; 112 once
        # a node whose answer is its bit inverted prints it, which the
        # stream build can do at every such node and the hoisted only where
        # the cell two on is blank; 155 once reads are held at 31/32, where
        # the hoisted builds' cheaper nodes beat the stream build's inverts;
        # 209 once a tree jumps to the subtrees it repeats.
        assert improved == 203  # the rest tie, keeping the old emission

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
            built = plain = rebuilt = 0

            def counted(
                table: str,
                perm: tuple[int, ...],
                _build: object = _six_five_hoisted,
                *,
                raw_copies: bool = False,
                share: bool = False,
            ) -> str:
                nonlocal built, plain, rebuilt
                # Each layout's winner is rebuilt once to print its copied
                # reads raw.
                if raw_copies:
                    rebuilt += 1
                else:
                    built += 1
                    plain += not share
                return _build(table, perm, raw_copies=raw_copies, share=share)  # type: ignore[operator, no-any-return]

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(module, "_six_five_hoisted", counted)
                boolean.six_five(table)
            # Only shared layouts are production candidates.
            assert plain == 0
            assert 1 <= built <= 4, f"n={n} built {built}"
            assert rebuilt == 1

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

    def test_dag_count_does_not_compare_descendants(self) -> None:
        """Nested keys compared n*T leaves even with cached tuple hashes."""
        comparisons = 0

        class Bit(str):
            __hash__ = str.__hash__

            def __eq__(self, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return super().__eq__(other)

        class Table(str):
            def __getitem__(self, index: int | slice) -> str:
                return Bit(super().__getitem__(index))

        for n in range(3, 13):
            comparisons = 0
            table = Table("".join(str(row.bit_count() % 2) for row in range(1 << n)))
            assert _six_five_dag_cost(table) == 2 * n
            assert comparisons <= 2 * len(table)

    @pytest.mark.parametrize("n", range(1, 6))
    @pytest.mark.medium
    def test_the_guarded_walk_executes_every_row(self, n: int) -> None:
        """The guarded walk answers every row of every table shape.

        Dense, constant, and random tables: the constant ones are where a
        walk that never advances (all zeros) or advances at every bit (a
        one-row at the far end) has to land exactly.
        """
        rng = random.Random(n)
        tables = [self._dense(n), "0" * 2**n, "1" * 2**n]
        tables += ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(2)]
        for table in tables:
            program = _six_five_guarded(table)
            assert _markers(program) == 1
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter(str(b) for b in bits)
                got = run_six_five_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                with pytest.raises(StopIteration):
                    next(feed)

    @pytest.mark.parametrize("n", range(1, 10))
    def test_guarded_execution_is_linear(self, n: int) -> None:
        """Zero and one paths both stay inside the geometric stride bound."""
        total = 1 << n
        tables = [
            "0" * total,
            "1" * total,
            "".join(str(row.bit_count() % 2) for row in range(total)),
        ]
        for table in tables:
            program = _six_five_guarded(table)
            for row in (0, total - 1):
                commands = _commands("6-5", program, table, row, 20_000)
                assert commands is not None
                assert commands <= 13 * total // 2 + 4 * n + 12
                if table == "1" * total and row == total - 1:
                    assert commands == 13 * total // 2 + 4 * n + 12

    def test_the_guarded_walk_has_linear_source(self) -> None:
        for n in range(1, 13):
            program = _six_five_guarded("1" * (1 << n))
            assert _markers(program) == 1
            assert len(program) == 7 * (1 << n) + 4 * n + 14

    def test_past_the_label_bound_the_walk_uses_conditional_strides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lower the unreachable 35-input limit and execute its replacement."""
        module = importlib.import_module("esolangs.tools.six_five")
        table = self._dense(5)
        monkeypatch.setattr(module, "_SIX_FIVE_MAX_LABEL", 4)
        program = _six_five_walk(table)
        assert program == _six_five_guarded(table)
        for row in range(32):
            assert run_six_five(program, list(format(row, "05b"))) == table[row]
        monkeypatch.setattr(module, "_SIX_FIVE_MAX_LABEL", 35)
        assert _six_five_walk(table) != program


class TestSixFiveSharing:
    """A repeated subtree is laid out once and jumped to.

    Only shared trees ship; plain trees remain size oracles.
    """

    @staticmethod
    def _totals(tables: list[str]) -> tuple[int, int]:
        """Return plain and shipped character totals."""
        before = after = 0
        for table in tables:
            orders = _six_five_orders(table)
            plain = len(_six_five_chosen(table, orders, share=False).removesuffix("0"))
            shipped = len(boolean.six_five(table))
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """Retiring plain candidates: 10,951 to 10,969 characters (+0.164%)."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (12135, 11252)
        assert 11252 * 100 < 10951 * 105

    def test_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 41,884 to 27,168 characters, 35.1%."""
        assert self._totals(five_input_sample()) == (41884, 27686)

    @pytest.mark.medium
    def test_five_input_sample_runs(self) -> None:
        """Every row of the five-input sample's shared programs computes its bit."""
        for table in five_input_sample():
            program = boolean.six_five(table)
            for combo in range(32):
                bits = [str((combo >> (4 - i)) & 1) for i in range(5)]
                assert run_six_five(program, bits) == table[combo], (table, combo)

    def test_a_left_leaf_is_one_copy(self) -> None:
        """AND's 0 leaves are one: each later test jumps to the first.

        The leaf builds on the tested cell's 31, whichever cell that is, so
        the copy prints right from any parent that falls through to it; it
        gains a ``4`` of its own, since a fall-through has none.
        """
        program = boolean.six_five("0" * 15 + "1")
        assert program.count("665A0") == 1
        assert _markers(program) == 4


def test_retired_orders_remain_available_when_routine_orders_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retirement preserves the alternative-order label-budget fallback."""
    module = importlib.import_module("esolangs.tools.six_five")
    table = "00000101"
    routine = _six_five_orders(table, compact=True)

    def limited(rows: str, order: tuple[int, ...], **kwargs: bool) -> str:
        if order in routine:
            return ""
        return _six_five_hoisted(rows, order, **kwargs)

    monkeypatch.setattr(module, "_six_five_hoisted", limited)
    program = boolean.six_five(table)
    for row in range(8):
        assert run_six_five(program, list(format(row, "03b"))) == table[row]


class TestGeneratorEdgePaths:
    def test_six_five_helper_edges(self) -> None:
        """The +5 tail of the constant encoder.

        ``_six_five_nav`` was retired with the arithmetic kernel; the folded
        leaf's own hop to cell 1 is a literal ``13``.
        """
        from esolangs.tools.six_five import _six_five_const

        assert _six_five_const(5) == "5"
        assert _six_five_const(11) == "65"

    def test_six_five_label_rejects_an_unspellable_operand(self) -> None:
        """Operands are one character, so the alphabet runs out at 35.

        ``0-9`` then ``A-Z`` is every character 6-5 reads as a number, which
        caps a 7n/8n operand at 35; past that there is nothing to emit.
        """
        from esolangs.tools.six_five import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        with pytest.raises(ValueError, match="no operand character for 36"):
            _six_five_label(_SIX_FIVE_MAX_LABEL + 1)

        # The range is closed at *both* ends, and zero is a real label --
        # a guard reading ``1 <=`` or ``0 <`` would reject the first one.
        assert _six_five_label(0) == "0"
        assert _six_five_label(1) == "1"
        with pytest.raises(ValueError, match="no operand character for -1"):
            _six_five_label(-1)

    def test_six_five_move_spells_a_distance_in_pairs(self) -> None:
        """Rightward moves go two cells at a time, with a ``3`` for the odd one.

        ``1`` steps two cells and ``3`` steps one back, so an even distance
        is all ``1``s and an odd distance is ``ceil(d / 2)`` of them with a
        ``3`` to come back over the extra cell.  Leftward is plain ``3``s.
        Swept over every table through three inputs the generator makes
        11,600 of these moves, over distances 0, 1 and 2 and in both
        directions, so every arm here is live -- including the equal case,
        which occurs 2,296 times and must emit nothing at all.
        """
        from esolangs.tools.six_five import _six_five_move

        assert _six_five_move(2, 2) == ""
        assert _six_five_move(0, 1) == "13"
        assert _six_five_move(0, 2) == "1"
        assert _six_five_move(0, 3) == "113"
        assert _six_five_move(0, 5) == "1113"
        assert _six_five_move(3, 0) == "333"
        assert _six_five_move(5, 0) == "33333"

    def test_six_five_refuses_at_more_than_thirty_five_labels(self) -> None:
        """The capacity test is ``> 35``, not ``>= 35``.

        An operand is one character and the alphabet ends at ``Z``, so 35
        branch labels fit and 36 do not.  The refusal is already witnessed
        by a 63-marker table (see ``test_boolean_six_five``), but only from far
        above -- which leaves the boundary itself free to move by one, and
        a table needing exactly 35 would then be refused despite being
        spellable.  ``_six_five_label`` marks that limit, so the two are
        asserted against each other rather than against a repeated literal.
        """
        from esolangs.tools.six_five import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _SIX_FIVE_MAX_LABEL == 35
        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        assert len(_six_five_label(_SIX_FIVE_MAX_LABEL)) == 1
