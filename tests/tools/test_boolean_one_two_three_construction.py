"""123 constructor fill resolution and work-budget checks."""

import pytest


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

    def test_painting_past_the_budget_is_refused(self) -> None:
        """``_paint_all`` prices its whole paint before writing any of it."""
        from esolangs.tools.one_two_three.construction import (
            _Builder,
            _paint_all,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        row = _Row((0,))
        row.pos = 1
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = [row]
        # Two offsets, so the paint is priced over both before any is
        # written -- one would leave the second offset's cost uncounted.
        # One of them is exactly 1, which has no shrunk ``k - 1`` pair to
        # paint: the guard that skips it is the only thing keeping a pair
        # of empty strings out of the price.
        _work[0] = 1  # _paint_all is called outside construct() here
        with pytest.raises(_WorkExhaustedError):
            _paint_all(b, (1, 3))
