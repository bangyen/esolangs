r"""Unit tests for the tape-based boolean generators."""

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
    _six_five_walk,
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
    r"""The widest row of a grid program, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


def _markers(program: str) -> int:
    r"""How many ``4`` markers a 6-5 program really has."""
    from esolangs.interpreters.tape_based.six_five import _tokens

    return sum(1 for token in _tokens(program) if token == "4")


def _leaves(table: str) -> int:
    r"""How many leaves a tree that folds constant subtrees spends on."""
    if len(set(table)) == 1:
        return 1
    half = len(table) // 2
    return _leaves(table[:half]) + _leaves(table[half:])


class TestSixFive:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.six_five(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_structure(self) -> None:
        r"""Both builds read, normalize to 8/9, branch on ``78``, and halt."""

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
        r"""A constant subtree emits one leaf instead of a full branch set."""
        mixed = {
            1: "10",
            2: "1010",
            3: "10010110",
            4: "1001011001101001",
            5: "10010110" * 4,
        }[n]
        assert len(boolean.six_five(table)) < len(boolean.six_five(mixed))
        # One ``A`` per emitted leaf:.
        # the number of distinct.
        assert boolean.six_five(table).count("A") == _leaves(table)

    @pytest.mark.parametrize(
        ("table", "n"),
        [("11", 1), ("1111", 2), ("11110000", 3), ("1000000000000000", 4)],
    )
    def test_folded_leaf_still_reads_every_input(self, table: str, n: int) -> None:
        r"""Every path through a folded node-read tree reads all ``n`` inputs."""

        program = _six_five_stream_ordered(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

        # Walk the emitted tree: a.
        # halves follow; a leaf carries.
        def reads_on_each_path(code: str) -> set[int]:
            if not code.startswith("B" + "2" * 8):  # a leaf.
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
            ("0" * 63 + "1", 6, 6),  # AND6: was refused by both.
            ("1" * 32 + "0" * 32, 6, 1),  # one split.
            ("1" * 48 + "0" * 16, 6, 2),  # two regions.
            ("1" * 64, 6, 0),  # constant.
            ("0" * 255 + "1", 8, 8),  # AND8.
        ],
    )
    def test_tree_past_five_inputs(self, table: str, n: int, labels: int) -> None:
        r"""A folded tree that fits the label budget is used at any ``n``."""
        program = boolean.six_five(table)
        assert _markers(program) == labels <= 35
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_six_five(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_marker_precheck_matches_emitted_tree(self) -> None:
        r"""The label count is what the emitted tree actually allocates."""
        for table in (
            "0" * 63 + "1",
            "1" + "0" * 63,
            "1" * 48 + "0" * 16,
            "1" * 64,
            "1" * 127 + "0",
            "0" * 255 + "1",
        ):
            assert _six_five_markers(table) == _markers(boolean.six_five(table))

        # And the bound itself, over.
        # fold more subtrees, never.
        # more labels than the.
        for value in range(256):
            table = format(value, "08b")
            assert _markers(boolean.six_five(table)) <= _six_five_markers(table)

    def test_folding_is_still_per_order_even_though_sharing_is_not(self) -> None:
        r"""Parity resists folding under every order, and is built anyway."""
        parity = "".join(str(bin(row).count("1") % 2) for row in range(64))
        for perm in permutations(range(6)):
            assert _six_five_markers(permute_truth_table(parity, perm)) == 63
        assert _six_five_dag_cost(parity) == 12 <= 35
        assert boolean.six_five(parity)

    def test_reordering_widens_what_renders(self) -> None:
        r"""A table that overflows in stream order can fold under another."""
        for table, folded in (("10010110" * 8, 7), (("10" * 64)[:64], 1)):
            assert _six_five_markers(table) == 63 > 35  # refused in stream order.
            best = min(
                _six_five_markers(permute_truth_table(table, perm))
                for perm in permutations(range(6))
            )
            assert best == folded <= 35
            program = boolean.six_five(table)
            # At most the folded count: the.
            assert _markers(program) <= folded
            for combo in range(64):
                bits = [(combo >> (5 - i)) & 1 for i in range(6)]
                got = run_six_five(program, [str(b) for b in bits])
                assert got == table[combo], f"inputs {bits}"

    def test_greedy_order_can_be_the_only_renderable_one(self) -> None:
        r"""Past the search cap, the greedy pick alone can carry a table."""
        n = 7
        alternating = ("10" * 128)[: 2**n]
        assert _six_five_markers(alternating) == 2**n - 1 > 35
        with pytest.raises(ValueError, match="35 branch labels"):
            _six_five_stream_ordered(alternating)
        # The identity order no longer.
        # the shared build takes it --.
        # whose distinct subtrees are a.
        assert _six_five_hoisted(alternating, tuple(range(n)))

        program = boolean.six_five(alternating)
        assert _markers(program) == 1  # greedy tests the last input.
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            feed = iter([str(b) for b in bits])
            assert run_six_five_from(program, feed) == alternating[combo]
            assert not list(feed), f"inputs {bits} left input unread"

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
    def test_total_through_five_inputs(self, n: int) -> None:
        r"""Every table up to five inputs renders: the worst case still fits."""
        alternating = ("10" * 2**n)[: 2**n]
        assert _six_five_markers(alternating) == 2**n - 1 <= 35
        boolean.six_five(alternating)  # renders rather than raising.

    def test_parity_is_the_easy_case_once_subtrees_are_shared(self) -> None:
        r"""Sharing inverts which table is the worst case."""
        parity6 = "".join(str(bin(row).count("1") % 2) for row in range(64))
        assert _six_five_markers(parity6) == 63 > 35
        assert _six_five_dag_cost(parity6) == 12 <= 35
        assert boolean.six_five(parity6)

        parity10 = "".join(str(bin(row).count("1") % 2) for row in range(1024))
        assert _six_five_dag_cost(parity10) == 20 <= 35
        assert boolean.six_five(parity10)

    @staticmethod
    def _dense(n: int) -> str:
        r"""A hash-derived table with no structure for the trees to exploit."""
        digest = hashlib.sha256(f"dense:{n}".encode()).digest()
        bits: list[str] = []
        block = 0
        while len(bits) < 2**n:
            digest = hashlib.sha256(digest + bytes([block & 255])).digest()
            bits.extend(str(byte & 1) for byte in digest)
            block += 1
        return "".join(bits[: 2**n])

    def test_a_table_whose_distinct_subtrees_overflow_takes_the_walk(self) -> None:
        r"""A table past the shared budget goes on the tape instead."""
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
        r"""The generator clears n == 10 on a table with nothing to fold."""
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
        r"""No table comes out longer than its identity-order program."""

        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(boolean.six_five(table))
            identity = len(_six_five_stream_ordered(table))
            assert dispatched <= identity, table
            improved += dispatched < identity
        # 186 before the leaves gained.
        # shortcut: a shorter leaf.
        # so more tables now beat the.
        assert improved == 208  # the rest tie, keeping the old.

    @pytest.mark.parametrize(
        ("table", "n"),
        [("0110", 2), ("10010110", 3), ("1001011001101001", 4)],
    )
    def test_every_path_consumes_exactly_n_inputs(self, table: str, n: int) -> None:
        r"""Each run reads all ``n`` inputs and no more, whichever build won."""
        program = boolean.six_five(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            feed = iter([str(b) for b in bits])
            got = run_six_five_from(program, feed)
            assert got == table[combo], f"inputs {bits}"
            assert not list(feed), f"inputs {bits} left input unread"

    def test_wide_tables_do_not_search_every_order(self) -> None:
        r"""Past the cap only the identity and a greedy order are built."""
        import importlib

        # The package re-exports the.
        # name, so import the module.
        module = importlib.import_module("esolangs.tools.boolean.six_five")

        # AND-n is symmetric, so its.
        # two dedupe to a single build.
        # 40320.
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
        r"""Retired construction helpers do not return as dispatch candidates."""
        import importlib

        # The package re-exports the.
        # name, so import the module.
        module = importlib.import_module("esolangs.tools.boolean.six_five")

        assert not hasattr(boolean, "six_five_arithmetic")
        assert module.__all__ == ["six_five"]
        assert not hasattr(module, "_SixFiveAsm")  # the assembler went too.
        assert not hasattr(module, "_six_five_nav")
        assert not hasattr(module, "_six_five_node_read")


# 2.3s over 84 tests: runs the.
@pytest.mark.medium
class TestStreetcode:
    def test_default_uses_only_shared_layouts(self) -> None:
        r"""Per-input loops are width fallbacks, never default candidates."""
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
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.streetcode(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_subtrees_fold(self) -> None:
        r"""A subtree whose rows agree prints instead of driving down halls."""
        constant = len(boolean.streetcode("11111111"))
        halves = len(boolean.streetcode("11110000"))
        scattered = len(boolean.streetcode("10101010"))
        assert constant < scattered
        assert halves < scattered
        # a folded leaf still prints.
        for table in ("11111111", "11110000", "11001100"):
            program = boolean.streetcode(table)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = run_streetcode(program, [str(b) for b in bits])
                assert got == table[combo], f"{table} inputs {bits}"

    def test_folded_leaf_keeps_the_cell_pointer_advances(self) -> None:
        r"""A folded leaf spends the ``=`` its skipped halls would have."""
        program = boolean.streetcode("00000000")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            assert run_streetcode(program, [str(b) for b in bits]) == "0"

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        r"""The tree splits in whichever order folds most, not input order."""
        scattered = len(boolean.streetcode("10101010"))
        aligned = len(boolean.streetcode("11110000"))
        parity = len(boolean.streetcode("01101001"))
        # Both are one-dependency.
        # one down to the aligned one's.
        # longer, and those characters.
        # cell the root's hall tests --.
        # in the prefix rather than per.
        assert aligned < scattered < parity
        assert scattered - aligned < 0.05 * aligned

    def test_input_reordering_never_grows_a_program(self) -> None:
        r"""The identity order is built first and ties keep it."""
        parity = boolean.streetcode("01101001")
        # Parity is the table where.
        # program is the identity one.
        assert "_I" not in parity

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_programs_compute_the_table(self, table: str) -> None:
        r"""A reordered program still computes its function."""
        program = boolean.streetcode(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_streetcode(program, [str(b) for b in bits])
            assert got == table[combo], f"{table} inputs {bits}"

    def test_reordering_keeps_the_reads_in_stream_order(self) -> None:
        r"""Reordering moves where a bit is stored, never when it is read."""
        for table in ("10101010", "11110000", "01101001"):
            assert boolean.streetcode(table).count("I") == 3

    def test_width_is_a_shape_choice(self) -> None:
        r"""A width picks a narrower shape, and that shape still computes."""
        table = "10"
        default = boolean.streetcode(table)
        narrow = boolean.streetcode(table, 25)
        assert _columns(narrow) <= 25 < _columns(default)
        assert narrow.count("\n") > default.count("\n")
        for bit in ("0", "1"):
            assert run_streetcode(narrow, [bit]) == table[int(bit)]

    def test_width_takes_the_narrowest_when_none_fits(self) -> None:
        r"""Below every shape's width the narrowest one is returned."""
        table = "10"
        program = boolean.streetcode(table, 1)
        assert _columns(program) == min(
            _columns(boolean.streetcode(table, w)) for w in (1, 25, 100)
        )
        for bit in ("0", "1"):
            assert run_streetcode(program, [bit]) == table[int(bit)]

    def test_width_none_is_unchanged(self) -> None:
        r"""Passing no width builds exactly what the generator always built."""
        for table in ("10", "0110", "11111110"):
            assert boolean.streetcode(table, None) == boolean.streetcode(table)

    def test_a_requested_width_is_never_overrun(self) -> None:
        r"""A width that *can* be met is met, measured on the emitted columns."""
        for table, width in (("0001", 33), ("0110", 33), ("01", 29)):
            program = boolean.streetcode(table, width)
            assert _columns(program) <= width, (table, width)

    def test_the_narrowest_fallback_is_really_the_narrowest(self) -> None:
        r"""Below every shape's width, the narrowest shape comes back."""
        program = boolean.streetcode("0100", 1)
        assert _columns(program) == 33
        for combo in range(4):
            bits = [str((combo >> 1) & 1), str(combo & 1)]
            assert run_streetcode(program, bits) == "0100"[combo]

    def test_a_width_equal_to_a_shape_is_wide_enough(self) -> None:
        r"""The fit test is inclusive: exactly the shape's width fits it."""
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
        r"""The layout is deterministic down to the character."""
        assert len(boolean.streetcode(table)) == length

    def test_no_trailing_blank_row(self) -> None:
        r"""The grid ends on its last real row."""
        for table in ("01", "0101", "0110", "11111110"):
            program = boolean.streetcode(table)
            assert not program.endswith("\n"), table
            assert program.split("\n")[-1].strip(), table

    def test_the_program_is_only_streetcode_characters(self) -> None:
        r"""Only the glyphs Streetcode reads, plus layout space."""
        allowed = set(" +-;=CIOU^_|~\n")
        for table in ("01", "0000", "0110", "11111110"):
            assert set(boolean.streetcode(table)) <= allowed, table
        for width in (1, 20, 29, 33):
            assert set(boolean.streetcode("0110", width)) <= allowed, width

    def test_order_search_stops_at_the_cap(self) -> None:
        r"""Past the cap only the identity order is offered."""
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
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111111111111", 4),  # constant one.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.dimensional(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_moves_are_pinned_to_dimension_zero(self) -> None:
        r"""A bare >/< would take its dimension from the cell's value."""
        program = boolean.dimensional("0110")
        rest = program.replace(">0", "").replace("<0", "")
        assert ">" not in rest
        assert "<" not in rest

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        r"""The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1")
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"


class TestDimensionalTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111100000000", 4),
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.dimensional_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_dimensional(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        r"""The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.dimensional_tree(xor6)) < 10_000

    def test_dimensional_is_the_tree(self) -> None:
        r"""dimensional is the tree, sparse or dense."""
        sparse = "0" * 15 + "1"  # AND4.
        assert boolean.dimensional(sparse) == boolean.dimensional_tree(sparse)
        xor = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        assert boolean.dimensional(xor) == boolean.dimensional_tree(xor)


class TestCirclefuck:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111111111111", 4),  # constant one.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
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
        r"""circlefuck_byte outputs the given byte per input combination."""
        program = boolean.circlefuck_byte(values)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == chr(values[combo]), f"inputs {bits}"

    def test_byte_values_require_a_power_of_two_table(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.circlefuck_byte([1, 2, 3])

    def test_past_the_cap_the_greedy_order_replaces_the_search(self) -> None:
        r"""Above ``_ORDER_SEARCH_MAX`` one greedy pick stands in for ``n!``."""
        import importlib

        # The package re-exports the.
        # name, so import the module.
        module = importlib.import_module("esolangs.tools.boolean.tape")
        from esolangs.tools.boolean.tape import _circlefuck_ordered

        table = "01" * 64  # alternating: the greedy pick.
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
        r"""A constant slice prints its answer instead of branching further."""
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
        r"""A folded leaf builds its value on a cleared cell."""
        program = boolean.circlefuck("11111111")
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = run_circlefuck(program, [str(b) for b in bits])
            assert got == "1", f"inputs {bits}"


class TestBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111111111111", 4),  # constant one.
            ("1000000000000000", 4),  # single one (AND4).
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_bf_is_the_tree(self) -> None:
        r"""bf is the folded tree, for constant and sparse tables alike."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        for table in ("0" * 16, "0" * 15 + "1", xor6):  # constant, AND4, dense.
            assert boolean.brainfuck(table) == boolean.bf_tree(table)


class TestBfTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1111111100000000", 4),
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.bf_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        r"""The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.bf_tree(xor6)) < 10_000

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice emits a leaf instead of branching on more bits."""
        assert len(boolean.bf_tree("11110000")) < len(boolean.bf_tree("10010110"))

    def test_parity_table_is_unfolded(self) -> None:
        r"""A table with no constant subtree still spends a leaf per row."""
        xor3 = "10010110"
        assert boolean.bf_tree(xor3).count("[-") == 14
        assert boolean.bf_tree("11110000").count("[-") == 2


class TestThreeDBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111111111111", 4),  # constant one.
            ("1000000000000000", 4),  # single one (AND4).
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.three_d_brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_three_d_brainfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_array_moves_use_the_3d_axes(self) -> None:
        r"""3D Brainfuck's >/< are no-ops, so the array moves with e/w."""
        program = boolean.three_d_brainfuck("0110")
        assert ">" not in program
        assert "<" not in program
        assert "e" in program
        assert "w" in program


class TestFactor:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.factor(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_factor(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_is_the_decimal_encoding_of_the_bf_program(self) -> None:
        r"""factor delegates to the brainfuck generator, then encodes it."""
        from esolangs.tools.boolean.tape import _factor_encode

        table = "0110"
        assert boolean.factor(table) == str(_factor_encode(boolean.brainfuck(table)))

    def test_sparse_tables_stay_small_at_n_four(self) -> None:
        r"""Sparse tables (few one-rows) encode a short brainfuck program, so."""
        assert boolean.factor("0" * 16).isdigit()
        assert boolean.factor("1" * 16).isdigit()

    def test_a_table_past_cpythons_own_limit_still_renders(self) -> None:
        r"""XOR6 encodes to 5934 digits, past CPython's 4300-digit default."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        program = boolean.factor(xor6)
        assert program.isdigit()
        assert len(program) > sys.get_int_max_str_digits()

    def test_the_render_leaves_the_global_limit_alone(self) -> None:
        r"""The digit limit is process-global, so it is borrowed, not kept."""
        before = sys.get_int_max_str_digits()
        boolean.factor(
            "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        )
        assert sys.get_int_max_str_digits() == before

    def test_max_digits_bounds_one_call(self) -> None:
        r"""``max_digits`` is the cap, and it names the size it refused."""
        before = sys.get_int_max_str_digits()
        xor4 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(16))
        with pytest.raises(ValueError, match="about 1703 digits"):
            boolean.factor(xor4, max_digits=1000)
        assert sys.get_int_max_str_digits() == before


class TestSlowAcvMammalian:
    r"""The decision tree LEAPFROG makes possible."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            # These carried ``slow`` while.
            # worst, 1.68s after the.
            # construction is closed-form.
            # case is dominated by the.
            # 2026-09-05 at 0.07s -- so.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.slow_acv_mammalian(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_slow_acv_mammalian(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_tables_still_read_every_input(self) -> None:
        r"""A constant table consumes all ``n`` inputs."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.slow_acv_mammalian import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        for table in ("0000", "1111", "0110"):
            program = boolean.slow_acv_mammalian(table)
            assert program.split().count("ACCEPT") == 3  # 2**2 - 1 nodes.
            io_obj = ScriptedIO("0\n" * 8)
            run_until_halt_or_cycle(_Machine(program, io_obj))
            assert io_obj.position() == 2

    def test_pointer_never_leaves_array_zero(self) -> None:
        r"""No ``SPRINT``: the tree lives in code space, not in array space."""
        program = boolean.slow_acv_mammalian("01101001")
        assert "SPRINT" not in program
        assert "CONFLAGRATE" not in program

    def test_a_node_opens_the_accumulator_on_a_clean_digit(self) -> None:
        r"""``ACCEPT`` is entered with ``acc % 256 == 48``, whatever the state."""
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
        r"""A 1-bit resumes exactly 15 tokens short of the array sum."""
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
        r"""The trampoline lands on its target from any head value."""
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
        r"""A hop of one token appends ``b == 1``, the least firing byte."""
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
        r"""No ``CONSUME``: the parent/child ballast lock never forms."""
        program = boolean.slow_acv_mammalian("0110")
        used = set(program.split())
        assert used <= {"SEED", "EXCRETE", "DIGEST", "ACCEPT", "PRONOUNCE", "LEAPFROG"}

    def test_a_stale_width_table_is_caught_not_emitted(self) -> None:
        r"""Slots too narrow for their trampolines raise, loudly."""
        import importlib

        # The package re-exports the.
        # name, so the package.
        # import_module reaches the.
        module = importlib.import_module("esolangs.tools.boolean.slow_acv_mammalian")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_widths", lambda n: [0] + [4] * n)
            with pytest.raises(AssertionError, match="slot"):
                module.slow_acv_mammalian("0110")

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
        r"""The cap recurrence's own output, pinned per level."""
        from esolangs.tools.boolean.slow_acv_mammalian import _widths

        assert _widths(n) == widths

    def test_the_slots_actually_hold_their_trampolines(self) -> None:
        r"""Every emitted hop fits, and level 1 is the tight one."""
        import importlib

        # The package re-exports the.
        # name, so the package.
        # import_module reaches the.
        module = importlib.import_module("esolangs.tools.boolean.slow_acv_mammalian")

        hops: list[int] = []
        original = module._trampoline  # noqa: SLF001

        def record(*args: object) -> tuple[list[str], list[int], int]:
            hop, array, acc = original(*args)
            hops.append(len(hop))
            return hop, array, acc

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_trampoline", record)
            for table in ("0110", "0001", "01101001"):
                module.slow_acv_mammalian(table)
        assert hops, "no trampoline was built"
        assert max(hops) == 306
        # Each slot is checked against.
        # (``_subtree`` raises on an.
        # that the deepest slot -- the.
        # need -- still clears the.
        assert max(hops) < max(module._widths(3)[1:])  # noqa: SLF001


class TestSuffolk:
    def test_candidate_costs_select_the_emitted_program(self) -> None:
        r"""The selector's model is exact across every non-constant table to."""
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
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1111111100000000", 4),  # top half.
            ("1000000000000000", 4),  # single one (AND4).
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_constant_tables_collapse_but_still_read(self) -> None:
        r"""A constant table skips the minterms but still reads its inputs."""
        for table in ("00", "11"):
            assert boolean.suffolk(table).count(",") == 1  # n == 1.

    def test_dense_tables_evaluate_the_complement(self) -> None:
        r"""A table with more ones than zeros is evaluated from its zero rows."""
        tables = (
            "10000000",  # 1 one.
            "10010000",  # 2.
            "11100000",  # 3.
            "11101000",  # 4.
            "11111000",  # 5.
            "11111001",  # 6.
            "11111110",  # 7.
        )
        lengths = [len(boolean.suffolk(table)) for table in tables]
        assert lengths[3] == max(lengths)  # four ones is the worst case.
        assert lengths[6] < lengths[3]  # seven ones is cheaper than.
        # and roughly as cheap as its.
        assert abs(lengths[6] - lengths[0]) < lengths[0] // 4

    @pytest.mark.parametrize(
        "table",
        ["11111110", "1111111111111110", "0111111111111111", "11111100"],
    )
    def test_complemented_tables_still_compute(self, table: str) -> None:
        r"""The inverted print stage answers the original table, not its flip."""
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
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1111111100000000", 4),  # top half.
            ("1000000000000000", 4),  # single one (AND4).
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.painfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_painfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_commands_are_preshifted_for_the_trans_table(self) -> None:
        r"""The interpreter shifts commands through its cycles, so the source."""
        from esolangs.interpreters.tape_based.painfuck import _translate

        program = boolean.painfuck("0110")
        translated = _translate(program)
        assert "a" in translated  # [ loops.
        assert "b" in translated  # ] loops.
        assert translated.count("a") == translated.count("b")
        assert "rl" in translated or "l" in translated  # pointer moves.


class TestBitTilde:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1000000000000000", 4),  # single one (AND4).
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.bit_tilde(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bit_tilde(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_single_read_and_output(self) -> None:
        r"""One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        assert program.startswith(")")
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")


class TestJaune:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("00", 1),  # constant zero.
            ("01", 1),  # identity.
            ("10", 1),  # NOT.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("0111", 2),  # OR.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.jaune(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_jaune(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            program = boolean.jaune(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_jaune(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_reads_every_input_whatever_the_table(self) -> None:
        r"""Every table consumes exactly ``n`` inputs, folds included."""
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
        r"""An input no node branches on is read without keeping a cell."""
        assert boolean.jaune("10101010").startswith("vvv")
        # every input matters here, so.
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
            pytest.param(99999, 99999, marks=pytest.mark.slow),  # 1.3s.
        ],
    )
    def test_multiply(self, a: int, b: int) -> None:
        r"""The sentinel-delimited multiply reads any-length operands."""
        program = boolean.jaune_multiply()
        lines = [*list(str(a)), "*", *list(str(b)), "#"]
        got = run_jaune(program, lines)
        assert got == str(a * b), f"{a} * {b}"

    def test_multiply_all_small_operands(self) -> None:
        r"""Every single-digit pair produces the right product."""
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
            ("01", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1111111111111111", 4),  # constant one.
        ],
    )
    def test_program_shape(self, table: str, n: int) -> None:
        r"""The program declares its cells, reads n inputs, and prints once."""
        program = boolean.basicfuck(table)
        assert program.startswith("#basicfuck t=unbounded r=0~255 o=wrap")
        assert (
            program.splitlines()[1]
            == "#allocate " + ", ".join(f"a{i}" for i in range(1, n + 1)) + ", out"
        )
        assert program.count("read ->") == n  # one read per input.
        # One leaf per *constant.
        # subtree whose rows agree, so.
        # a single row (parity) still.
        # table spends one.
        assert program.count("write <- out ;") == _leaves(table)

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice emits one leaf instead of branching further."""
        assert boolean.basicfuck("1" * 16).count("write <- out ;") == 1
        assert boolean.basicfuck("11110000").count("write <- out ;") == 2
        # parity has no constant slice.
        assert boolean.basicfuck("10010110").count("write <- out ;") == 8

    def test_decision_tree(self) -> None:
        r"""Each internal node branches both ways with the wiki's if!(...)."""
        program = boolean.basicfuck("0110")
        assert program.count("if (a1) {") == 1
        assert program.count("if !(a1) {") == 1
        assert program.count("if (a2) {") == 2
        assert program.count("if !(a2) {") == 2


class TestSbleq:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("0000000000000000", 4),  # constant zero.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.sbleq(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sbleq(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_structure(self) -> None:
        r"""The root reads, then its branch normalizes and tests it."""
        program = boolean.sbleq("0110")
        cells = [int(tok) for tok in program.split()]
        data_base = len(cells) - 11
        assert cells[:3] == [data_base + 4, -2, data_base + 6]  # root read.
        assert cells[6:9] == [  # root branch and normalization.
            data_base + 4,
            data_base,
            data_base + 8,
        ]
        assert cells[-11:-7] == [-49, 48, 49, -1]  # NEG49, D48, D49, HALT.
        code = cells[:data_base]
        triples = [tuple(code[i : i + 3]) for i in range(0, len(code), 3)]
        outputs = [t for t in triples if t[0] == -3]  # one output per leaf, in combo.
        assert outputs == [
            (-3, data_base + 1, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 1, 0),
        ]
        assert [t for t in triples if t == (0, 0, data_base + 3)] == 4 * [
            (0, 0, data_base + 3)
        ]  # one halt per leaf.

    def test_only_the_hoisted_route_remains(self) -> None:
        r"""The former node-read builder is gone, not merely bypassed."""
        import esolangs.tools.boolean.tape as module

        assert not hasattr(module, "_sbleq_node_read")

    def test_hoisted_build_reads_every_input_once_up_front(self) -> None:
        r"""The read block is 2n instructions and precedes every branch."""
        from esolangs.tools.boolean.tape import _sbleq_hoisted

        program = _sbleq_hoisted("00010111", (0, 1, 2))
        cells = [int(tok) for tok in program.split()]
        triples = [tuple(cells[i : i + 3]) for i in range(0, len(cells), 3)]
        reads = [t for t in triples[:6] if t[1] == -2]
        assert len(reads) == 3  # one read per input, all in.
        assert [t[0] for t in reads] == sorted({t[0] for t in reads})  # input order.

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
            ("10", 1),  # NOT.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("1000000000000000", 4),  # AND4.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.brainif(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_brainif(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        r"""The answer byte is built first, then an input is read and tested."""
        program = boolean.brainif("10")
        assert program.startswith("if 0 increment")
        assert "if 0 input" in program
        assert "if 48 goto" in program

    def test_the_answer_byte_is_built_once(self) -> None:
        r"""The climb to 48 is paid before the tree, not once per digit."""
        for table, one_leaves in (("10", 1), ("0110", 2), ("11111110", 3)):
            assert boolean.brainif(table).count("increment") == 48 + one_leaves

    def test_one_shared_output_tail(self) -> None:
        r"""Both answers print from the same two lines."""
        program = boolean.brainif("0110")
        assert program.count("output") == 2

    def test_constant_subtrees_fold(self) -> None:
        r"""A constant slice stops the branching, though not the reads."""
        assert len(boolean.brainif("11111111")) < len(boolean.brainif("11110000"))
        assert len(boolean.brainif("11110000")) < len(boolean.brainif("10010110"))


class TestRotfuck:
    r"""The ROTfuck boolean generator."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity.
            ("10", 1),  # NOT.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0111", 2),  # OR.
            ("0110", 2),  # XOR.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1111111100000000", 4),  # high half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every input combination produces the truth-table result."""
        program = boolean.rotfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_rotfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_program_round_trips_every_table_at_n_2(self) -> None:
        r"""Every two-input table produces the right result."""
        for table_int in range(2 ** (2**2)):
            table = format(table_int, "04b")
            program = boolean.rotfuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = run_rotfuck(program, [str(b) for b in bits])
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_the_rotation_cycle_is_the_documented_one(self) -> None:
        r"""``+ -> - -> > -> < -> , -> ."""
        from esolangs.tools.boolean.rotfuck import _ROTFUCK_CHAIN, _rotfuck_rot

        assert _ROTFUCK_CHAIN == "+-><,.[]"
        for i, char in enumerate(_ROTFUCK_CHAIN):
            forward = _ROTFUCK_CHAIN[(i + 1) % 8]
            assert _rotfuck_rot(char, 1) == forward, char
            assert _rotfuck_rot(forward, -1) == char, char
            assert _rotfuck_rot(char, 8) == char, char
            assert _rotfuck_rot(char, 0) == char, char

    def test_a_body_command_never_shows_as_a_bracket(self) -> None:
        r"""The allowed set at each offset is exactly the non-bracket rotations."""
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
        r"""Padding shifts the offset by two without moving the tape."""
        from esolangs.tools.boolean.rotfuck import _rotfuck_allowed, _rotfuck_neutral

        for offset in range(8):
            pad = _rotfuck_neutral(offset)
            assert pad in ("+-", "-+", "><", "<>"), offset
            assert set(pad) in ({"+", "-"}, {"<", ">"}), offset
            for i, char in enumerate(pad):
                assert char in _rotfuck_allowed((offset + i) % 8), (offset, char)
        # Forced where only one.
        assert _rotfuck_neutral(2) == "><"
        assert _rotfuck_neutral(3) == "+-"

    def test_every_body_is_seven_mod_eight_and_offset_legal(self) -> None:
        r"""The two invariants the block layout rests on, over many bodies."""
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
        r"""Nothing but the eight commands is emitted."""
        for table in ("01", "0110", "11110000", "01101001"):
            assert set(boolean.rotfuck(table)) <= set("+-><,.[]"), table

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 186),
            ("10", 188),
            ("0001", 303),
            ("0110", 418),
            ("11110000", 370),
            ("01101001", 935),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        r"""The layout is deterministic down to the character."""
        assert len(boolean.rotfuck(table)) == length
