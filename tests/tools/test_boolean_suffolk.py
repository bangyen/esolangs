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

    def test_constant_tables_collapse_but_still_read(self) -> None:
        """A constant table skips the minterms but still reads its inputs."""
        for table in ("00", "11"):
            assert boolean.suffolk(table).count(",") == 1  # n == 1

    def test_size_tracks_steps_rather_than_ones(self) -> None:
        """Cost is one op per *step* of a half-table, not per one-row."""
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
        """The inverted print stage answers the original table, not its flip."""
        n = (len(table) - 1).bit_length()
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"
