"""modulous generator tests."""

from esolangs import tools as boolean


class TestModulous:
    def test_narrow_literal_width_floor(self) -> None:
        assert max(map(len, boolean.modulous("0110", 1).splitlines())) == 3

    def test_fitting_bracket_layout_keeps_its_source(self) -> None:
        from esolangs.tools.wrap import _bracket_literal

        natural = boolean.modulous("01101001")
        assert boolean.modulous("01101001", 80) == _bracket_literal(natural, 80)

    def test_table_contents_do_not_change_size(self) -> None:
        """Equal arity gives equal size for folded and scattered tables."""
        sizes = {
            len(boolean.modulous(table))
            for table in ("11111111", "10010110", "00000000", "11110000")
        }
        assert len(sizes) == 1
