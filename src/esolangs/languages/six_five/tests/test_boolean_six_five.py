"""Covers :mod:`esolangs.languages.six_five.generator`."""

import importlib
from collections.abc import Iterator
from itertools import permutations

import pytest

import esolangs
from esolangs import run
from esolangs.generation.examples import BOOLEAN_EXAMPLES
from esolangs.generation.helpers import permute_truth_table
from esolangs.generation.wrap import (
    _six_five,
)
from esolangs.languages import generators as boolean
from esolangs.languages.six_five.generator import (
    _SIX_FIVE_TEST,
    _SIX_FIVE_TREE_NORMALIZE,
    _six_five_const,
    _six_five_guarded,
    _six_five_hoisted,
    _six_five_markers,
    _six_five_walk,
)
from tests.generators.boolean_runners import _run_from, _runner
from tests.generators.sample_tables import five_input_sample
from tests.support.witness_tables import dense as _dense
from tests.support.witness_tables import row_bits, witnesses

run_six_five = _runner("six_five")


def _identity(table: str) -> str:
    """The unshared tree in the table's own input order."""
    return _six_five_hoisted(table, tuple(range(len(table).bit_length() - 1)))


def run_six_five_from(program: str, feed: Iterator[str]) -> str:
    """Run a 6-5 program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.languages.six_five.interpreter", program, feed)


def _leaves(table: str) -> int:
    """How many leaves a tree that folds constant subtrees spends on ``table``."""
    if len(set(table)) == 1:
        return 1
    half = len(table) // 2
    return _leaves(table[:half]) + _leaves(table[half:])


def _markers(program: str) -> int:
    """How many ``4`` markers a 6-5 program really has."""
    from esolangs.languages.six_five.interpreter import _tokens

    return sum(1 for token in _tokens(program) if token == "4")


class TestSixFive:
    def test_branch_structure(self) -> None:
        """The build reads, normalizes to 31/32, branches on ``7V``, and halts."""

        program = _identity("0110")
        assert program.startswith("B")
        assert _SIX_FIVE_TREE_NORMALIZE in program
        assert _SIX_FIVE_TEST in program
        assert program.endswith("A0")
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

        program = _identity(table)
        for combo in range(2**n):
            bits = row_bits(combo, n)
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

    def test_folding_is_still_per_order_even_though_sharing_is_not(self) -> None:
        """Parity resists folding under every order, and is built anyway."""
        parity = "".join(str(bin(row).count("1") % 2) for row in range(64))
        for perm in permutations(range(6)):
            assert _six_five_markers(permute_truth_table(parity, perm)) == 63
        assert _markers(boolean.six_five(parity)) <= 35
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

    def test_the_alternating_table_is_one_shared_node(self) -> None:
        """The alternating table is NOT of its last input: one node carries it."""
        n = 7
        alternating = ("10" * 128)[: 2**n]
        assert _six_five_markers(alternating) == 2**n - 1 > 35
        # The identity order no longer returns "": its tree overflows, so
        # the shared build takes it -- this table is NOT of the last input,
        # whose distinct subtrees are a handful whatever the order.
        assert _six_five_hoisted(alternating, tuple(range(n)))

        program = boolean.six_five(alternating)
        # NOT of the last input is one node, whichever order wins.
        assert _markers(program) == 1
        for combo in range(2**n):
            bits = row_bits(combo, n)
            feed = iter([str(b) for b in bits])
            assert run_six_five_from(program, feed) == alternating[combo]
            assert not list(feed), f"inputs {bits} left input unread"

    def test_parity_is_the_easy_case_once_subtrees_are_shared(self) -> None:
        """Sharing inverts which table is the worst case."""
        parity6 = "".join(str(bin(row).count("1") % 2) for row in range(64))
        assert _six_five_markers(parity6) == 63 > 35
        assert _markers(boolean.six_five(parity6)) <= 35
        assert boolean.six_five(parity6)

        parity10 = "".join(str(bin(row).count("1") % 2) for row in range(1024))
        assert _markers(boolean.six_five(parity10)) <= 35
        assert boolean.six_five(parity10)

    def test_dense_seven_inputs_fit_the_shared_layout(self) -> None:
        """The actual layout fits where the retired DAG precheck rejected it."""
        table = _dense(7)
        program = boolean.six_five(table)
        assert _six_five_markers(table) > 35
        assert _markers(program) <= 35
        assert len(program) < len(_six_five_walk(table).removesuffix("0"))
        for row in range(128):
            feed = iter(format(row, "07b"))
            assert run_six_five_from(program, feed) == table[row]
            assert not list(feed)

    def test_a_table_whose_distinct_subtrees_overflow_takes_the_walk(self) -> None:
        """A table past the shared budget goes on the tape instead."""
        table = _dense(8)
        program = boolean.six_five(table)
        assert program == _six_five_walk(table).removesuffix("0")
        assert _markers(program) == 8
        for combo in range(0, 256, 3):
            got = run_six_five(program, list(format(combo, "08b")))
            assert got == table[combo], f"row {combo}"

    def test_an_ignored_input_on_the_walk_is_one_read(self) -> None:
        """``B1`` and its stride: five characters, never another table.

        Its ``4`` is gone too, so the labels count essential inputs; labelled
        by position, every later jump misroutes (all but a last ignored one
        computed wrong rows).
        """
        dense7 = _dense(7)
        for at in (0, 3, 7):
            low = 7 - at
            table = "".join(
                dense7[row >> (low + 1) << low | row & ((1 << low) - 1)]
                for row in range(256)
            )
            program = _six_five_walk(table).removesuffix("0")
            assert len(program) - len(_six_five_walk(dense7).removesuffix("0")) == 5, at
            assert _markers(program) == 7
            for combo in range(0, 256, 3):
                bits = [str((combo >> (7 - i)) & 1) for i in range(8)]
                assert run_six_five(program, bits) == table[combo], (at, combo)

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
        for table in witnesses(3):
            for perm in permutations(range(3)):
                program = _six_five_hoisted(permute_truth_table(table, perm), perm)
                assert "71" not in program
                for combo in range(8):
                    bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                    assert run_six_five(program, bits) == table[combo], (table, perm)

    def test_a_read_one_node_uses_is_normalized_there(self) -> None:
        """A read tested at one node alone costs its -17 on that node's paths."""
        # AND of x1 and x2, x2 tested first.  x1 is tested at one node
        # alone, so its read skips the -17 and its node pays it (the
        # normalize before the test); x0 counts two paths (a copy node),
        # so its read is normalized up front, and the copied bit prints
        # from the held 31 (+17 as ``665``), not from the raw read.
        program = _six_five_hoisted("00010001", (2, 1, 0))
        assert program.startswith("B99213B13B3" + _SIX_FIVE_TREE_NORMALIZE)
        assert program.endswith("4" + "3665A0")
        for value in range(256):
            table = format(value, "08b")
            for perm in permutations(range(3)):
                permuted = permute_truth_table(table, perm)
                program = _six_five_hoisted(permuted, perm)
                for combo in range(8):
                    bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                    assert run_six_five(program, bits) == table[combo], (table, perm)

    def test_reordering_only_shrinks(self) -> None:
        """No table comes out longer than its identity-order program."""

        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.six_five(table))
            # The dispatch drops a trailing ``0``; compare like with like.
            identity = len(_identity(table).removesuffix("0"))
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
        # 209 once a tree jumps to the subtrees it repeats; 196 once the
        # winner's raw-copy re-emission retired (candidate #11), down
        # from 219: its and/or-shaped wins now tie the stream build.
        assert improved == 196  # the rest tie, keeping the old emission

    def test_the_guarded_walk_has_linear_source(self) -> None:
        for n in range(1, 13):
            program = _six_five_guarded("1" * (1 << n))
            assert _markers(program) == 1
            assert len(program) == 7 * (1 << n) + 4 * n + 14

    def test_past_the_label_bound_the_walk_uses_conditional_strides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lower the unreachable 35-input limit and execute its replacement."""
        module = importlib.import_module("esolangs.languages.six_five.generator")
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


def test_the_walk_carries_a_table_when_no_tree_order_fits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With every tree order over the label budget, the walk takes over."""
    module = importlib.import_module("esolangs.languages.six_five.generator")
    table = "00000101"

    def over_budget(_rows: str, _order: tuple[int, ...], **_kwargs: bool) -> str:
        return ""

    monkeypatch.setattr(module, "_six_five_hoisted", over_budget)
    program = boolean.six_five(table)
    assert program == _six_five_walk(table).removesuffix("0")
    for row in range(8):
        assert run_six_five(program, list(format(row, "03b"))) == table[row]


class TestGeneratorEdgePaths:
    def test_six_five_helper_edges(self) -> None:
        """The +5 tail of the constant encoder."""

        assert _six_five_const(5) == "5"
        assert _six_five_const(11) == "65"
        # Below the 5k <= value window: ``6``s, then ``62`` pairs.
        assert _six_five_const(1) == "62"
        assert _six_five_const(7) == "662"

    def test_six_five_label_rejects_an_unspellable_operand(self) -> None:
        """Operands are one character, so the alphabet runs out at 35."""
        from esolangs.languages.six_five.generator import (
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
        from esolangs.languages.six_five.generator import _six_five_move

        assert _six_five_move(2, 2) == ""
        assert _six_five_move(0, 1) == "13"
        assert _six_five_move(0, 2) == "1"
        assert _six_five_move(0, 3) == "113"
        assert _six_five_move(0, 5) == "1113"
        assert _six_five_move(3, 0) == "333"
        assert _six_five_move(5, 0) == "33333"

    def test_six_five_refuses_at_more_than_thirty_five_labels(self) -> None:
        """The capacity test is ``> 35``, not ``>= 35``."""
        from esolangs.languages.six_five.generator import (
            _SIX_FIVE_MAX_LABEL,
            _six_five_label,
        )

        assert _SIX_FIVE_MAX_LABEL == 35
        assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"
        assert len(_six_five_label(_SIX_FIVE_MAX_LABEL)) == 1


def test_six_five_keeps_an_operand_with_its_command() -> None:
    """``7``/``8`` take the next character, so a break never lands between."""
    program = "657812A"
    for width in range(2, 10):
        for line in _six_five(program, width).split("\n"):
            assert not line.endswith(("7", "8")), f"width {width} split an operand"


def test_six_five_keeps_a_guard_with_the_instruction_it_skips() -> None:
    """``7n`` skips the next *token*, and a newline is one."""
    program = "70621A"
    stdin = BOOLEAN_EXAMPLES["6-5"].stdin
    unwrapped = run("6-5", program, stdin=stdin)
    for width in range(2, 12):
        assert run("6-5", _six_five(program, width), stdin=stdin) == unwrapped


def test_internal_route_budget_is_not_a_generator_restriction() -> None:
    assert esolangs.describe("6-5")["generator_restrictions"] is None
    assert esolangs.describe("6-5")["generator_max_inputs"] is None
