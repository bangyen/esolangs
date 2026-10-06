"""suffolk generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_suffolk,
)


class TestSuffolk:
    def test_streaming_fold_scales_linearly(self) -> None:
        """Doubling a dense table stays below twice plus fixed setup."""
        sizes = []
        for n in (8, 9, 10):
            table = "".join(str((i * 73 + i.bit_count()) & 1) for i in range(2**n))
            sizes.append(len(boolean.suffolk(table)))
        assert sizes == [2211, 3224, 5087]
        assert sizes[2] < 2 * sizes[1]

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
    @pytest.mark.medium
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

    def test_size_tracks_steps_rather_than_ones(self) -> None:
        """Cost is one op per *step* of a half-table, not per one-row.

        The countdown sweep emits an op only where consecutive rows differ,
        counting the drop off the end of each half, so the ones-count does
        not price a table: the step profile fixes the length exactly, and
        one one and seven ones land in different groups only because their
        steps fall in different halves.  This replaces a pin on the retired
        minterm route, whose cost rose with the evaluated row-set instead.

        **Every table here depends on all three inputs**, which the prefix
        family ``1^k 0^(8-k)`` does not: ``11110000`` ignores two of them,
        so dependency reduction rather than the sweep would be measured.
        """
        tables = (
            "10000000",  # 1 one
            "10010000",  # 2 ones
            "11100000",  # 3 ones
            "11101000",  # 4 ones
            "11111000",  # 5 ones
            "11111001",  # 6 ones
            "11111110",  # 7 ones
        )
        groups: dict[tuple[int, ...], set[int]] = {}
        for table in tables:
            half = len(table) // 2
            profile = tuple(
                sum(a != b for a, b in zip(part, f"{part[1:]}0", strict=True))
                for part in (table[:half], table[half:])
            )
            groups.setdefault(profile, set()).add(len(boolean.suffolk(table)))
        assert sorted(groups) == [(1, 0), (1, 1), (1, 3), (3, 0)]
        assert all(len(sizes) == 1 for sizes in groups.values())  # profile fixes it
        assert min(groups[(1, 0)]) < min(groups[(3, 0)])  # more steps cost more
        assert min(groups[(1, 1)]) < min(groups[(1, 3)])

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
