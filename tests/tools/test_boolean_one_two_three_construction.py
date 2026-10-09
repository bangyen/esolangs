"""123 constructor fill resolution checks."""


class TestConstructorWorkBudget:
    """Two paths that lost their exerciser with the text generators."""

    def test_a_fill_token_resolves_to_the_row_own_bit(self) -> None:
        """A tuple token is an input fill: the row decides its character."""
        from esolangs.tools.one_two_three.construction import (
            _ONE,
            _ZERO,
            _Row,
            _row_runs,
        )

        one = _Row((1,))
        zero = _Row((0,))
        assert _row_runs(one, [("x", 0)]) == [(_ONE, 1)]
        assert _row_runs(zero, [("x", 0)]) == [(_ZERO, 1)]

    def test_a_fill_coalesces_with_the_run_beside_it(self) -> None:
        """Adjacent equal characters become one run, fills included."""
        from esolangs.tools.one_two_three.construction import (
            _ONE,
            _Row,
            _row_runs,
        )

        row = _Row((1,))
        assert _row_runs(row, [_ONE * 2, ("x", 0)]) == [(_ONE, 3)]
