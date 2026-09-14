"""The pytest cost bands have hard, testable ceilings."""

import pytest

from tests.duration_policy import violation


@pytest.mark.parametrize(
    ("markers", "duration"),
    [
        (set(), 1.0),
        ({"medium"}, 5.0),
        ({"slow"}, 100.0),
        ({"weekly"}, 100.0),
        ({"medium", "slow"}, 100.0),
    ],
)
def test_duration_inside_its_band_is_accepted(
    markers: set[str], duration: float
) -> None:
    assert violation(markers, duration) is None


@pytest.mark.parametrize(
    ("markers", "duration", "message"),
    [
        (set(), 1.01, "fast band limit of 1s"),
        ({"medium"}, 5.01, "medium band limit of 5s"),
    ],
)
def test_duration_past_its_band_names_the_limit_and_remedy(
    markers: set[str], duration: float, message: str
) -> None:
    assert message in str(violation(markers, duration))
