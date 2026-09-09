"""The growth certificate's rejecting arms, one construction each.

:func:`_climbs_forever` certifies an affine climb from three visits to
one key.  Each of its four conditions refuses a different way the three
can fail to line up, and a program reaching every one of them is far
harder to write than the triples themselves.
"""

from esolangs.vm import _climbs_forever

# Three visits, ten steps apart, whose values climb by a constant 1 with
# the input cursor never moving: the shape the certificate accepts.
CLIMBING = [(0, (0,), 0), (10, (1,), 0), (20, (2,), 0)]


class TestClimbsForever:
    def test_a_constant_positive_step_with_held_clamps_is_certified(self) -> None:
        assert _climbs_forever(CLIMBING, [None] * 21) is True

    def test_a_moving_input_cursor_is_not_certified(self) -> None:
        """Consuming input between visits means the laps are not alike."""
        visits = [(0, (0,), 0), (10, (1,), 1), (20, (2,), 1)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_changing_value_count_is_not_certified(self) -> None:
        visits = [(0, (0,), 0), (10, (1, 1), 0), (20, (2, 2), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_two_different_steps_are_not_certified(self) -> None:
        """The second lap climbs by 2 where the first climbed by 1."""
        visits = [(0, (0,), 0), (10, (1,), 0), (20, (3,), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_step_that_stands_still_is_not_certified(self) -> None:
        visits = [(0, (5,), 0), (10, (5,), 0), (20, (5,), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_descending_step_is_not_certified(self) -> None:
        """Falling values reach a floor rather than climbing forever."""
        visits = [(0, (5,), 0), (10, (4,), 0), (20, (3,), 0)]
        assert _climbs_forever(visits, [None] * 21) is False

    def test_a_drifting_clamp_is_not_certified(self) -> None:
        """The step repeats, but a slack sinking toward zero will flip."""
        slacks: list[int | None] = [5] * 10 + [3] * 11
        assert _climbs_forever(CLIMBING, slacks) is False
