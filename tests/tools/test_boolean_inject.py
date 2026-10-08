"""inject generator tests."""

from itertools import pairwise

import pytest

import esolangs
from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_inject,
)


class TestInject:
    """The decision tree of ``skipq`` guards over stored input blocks."""

    def test_constant_subtrees_are_folded(self) -> None:
        """A table ignoring its later inputs costs one test, not ``n``."""
        one_dependency = len(boolean.inject("00001111"))
        parity = len(boolean.inject("01101001"))
        assert one_dependency < parity / 2

    def test_reads_every_input_before_branching(self) -> None:
        """The reads are hoisted, so every path consumes exactly ``n`` lines."""
        program = boolean.inject("0001").splitlines()
        reads = [i for i, line in enumerate(program) if line.startswith("readto")]
        first_branch = next(
            i for i, line in enumerate(program) if line.startswith("skipq")
        )
        assert len(reads) == 2, "one readto per input, and no more"
        assert max(reads) < first_branch, "every read precedes every branch"

    def test_every_label_occurs_exactly_twice(self) -> None:
        """Inject's labels are strictly two-occurrence: an open and a close."""
        from collections import Counter

        for table in ("01", "0001", "0110", "01101001", "11110000"):
            counts = Counter(
                line
                for line in boolean.inject(table).splitlines()
                if line.endswith(";")
            )
            assert all(v == 2 for v in counts.values()), (table, counts)

    def test_an_input_block_starts_empty(self) -> None:
        """An empty block is two *adjacent* delimiters, with nothing between."""
        for n, table in ((1, "01"), (2, "0001"), (3, "01101001")):
            lines = boolean.inject(table).splitlines()
            head = lines[: 2 * n]
            assert all(head[2 * d] == head[2 * d + 1] for d in range(n))
            assert len(set(head[::2])) == n

    def test_small_tree_uses_one_character_labels(self) -> None:
        """Inputs, branches, leaves, and constants share the short namespace."""
        labels = [
            line[:-1]
            for line in boolean.inject("01101001").splitlines()
            if line.endswith(";")
        ]
        assert all(len(label) == 1 for label in labels)

    def test_halving_lookup_executes_wide_rows(self) -> None:
        """Regex halves return sampled six-input rows."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = boolean.inject(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_inject(program, bits) == table[row] + "\n"

    @pytest.mark.parametrize("width", [1, 40, 80])
    def test_chunked_lookup_executes_every_row(self, width: int) -> None:
        """Leaf escapes join one postlude without losing the selected chunk."""

        for n in (5, 6, 7):
            table = "".join(str((row * 73 + row // 3) & 1) for row in range(1 << n))
            plain = boolean.inject(table)
            program = esolangs.generate("Inject", table, width=width)
            assert max(map(len, program.splitlines())) <= max(width, 22)
            assert program.count("readto ") == n
            if max(map(len, plain.splitlines())) <= width:
                assert program == plain
            for row in range(1 << n):
                assert run_inject(program, list(f"{row:0{n}b}")) == table[row] + "\n"

    def test_chunked_lookup_drops_ignored_inputs(self) -> None:
        """Input 2 of 7 is read and never tested; the table is indexed without it."""
        small = "".join(str((row * 73 + row // 3) & 1) for row in range(64))
        table = "".join(small[r >> 1 & 32 | r & 31] for r in range(128))
        program = esolangs.generate("Inject", table, width=1)
        assert program.count("readto ") == 7
        assert len(program) < 0.7 * len(
            esolangs.generate("Inject", small + small[::-1], width=1)
        )
        for row in range(128):
            assert run_inject(program, list(f"{row:07b}")) == table[row] + "\n"

    def test_chunked_source_growth_is_linear(self) -> None:
        sizes = [
            len(boolean.inject("01101001" * (2 ** (n - 3)), 1)) for n in (9, 10, 11)
        ]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_the_tree_collapses_on_the_constant_subtree_alone(self) -> None:
        """Depth never terminates the recursion; a constant subtree always does."""
        from esolangs.tools.inject import _Names, _tree

        calls: list[tuple[str, int, int]] = []

        def record(table: str, depth: int, n: int, state: dict[str, int]) -> None:
            calls.append((table, depth, n))
            if depth == n or table == table[0] * len(table):
                return
            half = len(table) // 2
            record(table[:half], depth + 1, n, state)
            record(table[half:], depth + 1, n, state)

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                record(format(table_int, f"0{2**n}b"), 0, n, {})
        collapsed_by_depth_only = [
            (t, d) for t, d, n in calls if d == n and t != t[0] * len(t)
        ]
        assert collapsed_by_depth_only == []
        # And the tree itself is unchanged when the depth clause cannot fire.
        perm = (0, 1, 2)
        assert _tree("01101001", 0, 3, _Names(3, perm), perm) == _tree(
            "01101001", 0, 3, _Names(3, perm), perm
        )
