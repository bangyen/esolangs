"""Covers :mod:`esolangs.tools.six_five`."""

import importlib
from itertools import permutations

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import permute_truth_table
from esolangs.tools.six_five import (
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
from tests.tools.boolean_runners import (
    run_six_five,
    run_six_five_from,
)
from tests.tools.sample_tables import five_input_sample
from tests.tools.test_boolean_contract import _dense
from tests.witness_tables import witnesses


def _leaves(table: str) -> int:
    """How many leaves a tree that folds constant subtrees spends on ``table``."""
    if len(set(table)) == 1:
        return 1
    half = len(table) // 2
    return _leaves(table[:half]) + _leaves(table[half:])


def _markers(program: str) -> int:
    """How many ``4`` markers a 6-5 program really has."""
    from esolangs.interpreters.tape_based.six_five import _tokens

    return sum(1 for token in _tokens(program) if token == "4")


class TestSixFive:
    def test_branch_structure(self) -> None:
        """Both builds read, normalize to 31/32, branch on ``7V``, and halt."""

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
        """A constant subtree emits one leaf instead of a full branch set."""
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
        """Every path through a folded node-read tree reads all ``n`` inputs."""

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

    def test_marker_precheck_matches_emitted_tree(self) -> None:
        """The label count is what the emitted tree actually allocates."""

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
        """Parity resists folding under every order, and is built anyway."""
        parity = "".join(str(bin(row).count("1") % 2) for row in range(64))
        for perm in permutations(range(6)):
            assert _six_five_markers(permute_truth_table(parity, perm)) == 63
        assert _six_five_dag_cost(parity) == 12 <= 35
        assert boolean.six_five(parity)

    def test_reordering_widens_what_renders(self) -> None:
        """A table that overflows in stream order can fold under another."""
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
        """Past the search cap, the greedy pick alone can carry a table."""
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

    def test_parity_is_the_easy_case_once_subtrees_are_shared(self) -> None:
        """Sharing inverts which table is the worst case."""
        parity6 = "".join(str(bin(row).count("1") % 2) for row in range(64))
        assert _six_five_markers(parity6) == 63 > 35
        assert _six_five_dag_cost(parity6) == 12 <= 35
        assert boolean.six_five(parity6)

        parity10 = "".join(str(bin(row).count("1") % 2) for row in range(1024))
        assert _six_five_dag_cost(parity10) == 20 <= 35
        assert boolean.six_five(parity10)

    def test_a_table_whose_distinct_subtrees_overflow_takes_the_walk(self) -> None:
        """A table past the shared budget goes on the tape instead."""
        dense7 = _dense(7)
        assert _six_five_dag_cost(dense7) > 35
        program = boolean.six_five(dense7)
        assert program == _six_five_walk(dense7).removesuffix("0")  # halts at its end
        assert _markers(program) == 7
        for combo in range(128):
            bits = [(combo >> (6 - i)) & 1 for i in range(7)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == dense7[combo], f"inputs {bits}"

    def test_dense_ten_inputs_render_and_run(self) -> None:
        """The generator clears n == 10 on a table with nothing to fold."""
        dense10 = _dense(10)
        program = boolean.six_five(dense10)
        assert _markers(program) == 10
        assert len(program) == 5308
        for combo in (0, 1, 512, 1023, *range(7, 1024, 128)):
            bits = [(combo >> (9 - i)) & 1 for i in range(10)]
            feed = iter([str(b) for b in bits])
            assert run_six_five_from(program, feed) == dense10[combo], f"row {combo}"
            assert not list(feed), f"inputs {bits} left input unread"

    def test_an_inverted_bit_skips_a_step_only_before_more_reads(self) -> None:
        """A node whose answer is NOT its bit tests it, unless reads remain."""
        assert _markers(boolean.six_five("10")) == 1
        assert "71" not in boolean.six_five("10")
        assert "71" in _six_five_stream_ordered("11110000")
        for table in witnesses(3):
            for perm in permutations(range(3)):
                program = _six_five_hoisted(permute_truth_table(table, perm), perm)
                # The identity order is the stream build's, not the hoisted.
                assert "71" not in program or perm == (0, 1, 2)
                for combo in range(8):
                    bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                    assert run_six_five(program, bits) == table[combo], (table, perm)

    def test_a_read_one_node_uses_is_normalized_there(self) -> None:
        """A read tested at one node alone costs its -17 on that node's paths."""
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
        table = _dense(5)
        monkeypatch.setattr(module, "_SIX_FIVE_MAX_LABEL", 4)
        program = _six_five_walk(table)
        assert program == _six_five_guarded(table)
        for row in range(32):
            assert run_six_five(program, list(format(row, "05b"))) == table[row]
        monkeypatch.setattr(module, "_SIX_FIVE_MAX_LABEL", 35)
        assert _six_five_walk(table) != program


class TestSixFiveSharing:
    """A repeated subtree is laid out once and jumped to."""

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

    @pytest.mark.medium
    def test_five_input_sample_runs(self) -> None:
        """Every row of the five-input sample's shared programs computes its bit."""
        for table in five_input_sample():
            program = boolean.six_five(table)
            for combo in range(32):
                bits = [str((combo >> (4 - i)) & 1) for i in range(5)]
                assert run_six_five(program, bits) == table[combo], (table, combo)

    def test_a_left_leaf_is_one_copy(self) -> None:
        """AND's 0 leaves are one: each later test jumps to the first."""
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
        """The +5 tail of the constant encoder."""

        assert _six_five_const(5) == "5"
        assert _six_five_const(11) == "65"

    def test_six_five_label_rejects_an_unspellable_operand(self) -> None:
        """Operands are one character, so the alphabet runs out at 35."""
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
        """Rightward moves go two cells at a time, with a ``3`` for the odd one."""
        from esolangs.tools.six_five import _six_five_move

        assert _six_five_move(2, 2) == ""
        assert _six_five_move(0, 1) == "13"
        assert _six_five_move(0, 2) == "1"
        assert _six_five_move(0, 3) == "113"
        assert _six_five_move(0, 5) == "1113"
        assert _six_five_move(3, 0) == "333"
        assert _six_five_move(5, 0) == "33333"

    def test_six_five_refuses_at_more_than_thirty_five_labels(self) -> None:
        """The capacity test is ``> 35``, not ``>= 35``."""
        from esolangs.tools.six_five import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _SIX_FIVE_MAX_LABEL == 35
        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        assert len(_six_five_label(_SIX_FIVE_MAX_LABEL)) == 1
