"""inject generator tests."""

from itertools import pairwise

import pytest

import esolangs
from esolangs import tools as boolean


class TestInject:
    """The decision tree of ``skipq`` guards over stored input blocks."""

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

    def test_every_label_occurs_exactly_twice(self) -> None:
        """Inject's labels are strictly two-occurrence: an open and a close.

        The construction leans on it -- each leaf carries *its own* escape
        label precisely because a third occurrence would not be a legal
        block, and the escape blocks are allowed to overlap only because
        each closes exactly once in the tail.  A counter that handed out a
        duplicate would still emit a program, and a table whose paths
        happen to avoid the clash would still compute correctly, so the
        rule is checked over the label set rather than through an answer.
        """
        from collections import Counter

        for table in ("01", "0001", "0110", "01101001", "11110000"):
            counts = Counter(
                line
                for line in boolean.inject(table).splitlines()
                if line.endswith(";")
            )
            assert all(v == 2 for v in counts.values()), (table, counts)

    def test_an_input_block_starts_empty(self) -> None:
        """An empty block is two *adjacent* delimiters, with nothing between.

        ``readto`` fills the block, so it has to start empty -- and empty
        means the two delimiter lines are adjacent and bare.  A stray
        space before the closing delimiter still parses and still computes
        the table, which is exactly why the spelling is asserted here
        instead of being left to the truth-table sweeps.
        """
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

    def test_halving_lookup_growth_is_linear(self) -> None:
        """Wide parity programs grow by at most the table-size ratio."""
        sizes = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(boolean.inject(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    @pytest.mark.parametrize("width", [1, 20, 40, 80])
    def test_chunked_layout(self, width: int) -> None:
        """Width selection preserves complete commands and hoisted reads."""

        for n in (5, 6, 7):
            table = "".join(str((row * 73 + row // 3) & 1) for row in range(1 << n))
            plain = boolean.inject(table)
            program = esolangs.generate("Inject", table, width)
            assert max(map(len, program.splitlines())) <= max(width, 22)
            assert program.count("readto ") == n
            if max(map(len, plain.splitlines())) <= width:
                assert program == plain

    def test_chunked_source_growth_is_linear(self) -> None:
        sizes = [
            len(boolean.inject("01101001" * (2 ** (n - 3)), 1)) for n in (9, 10, 11)
        ]
        assert all(b <= 2 * a for a, b in pairwise(sizes))
