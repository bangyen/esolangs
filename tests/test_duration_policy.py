"""The pytest cost bands have hard, testable ceilings."""

import pytest

from tests.duration_policy import CI_SCALE, limits, violation


@pytest.fixture(autouse=True)
def _local_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the local ceilings, so a run under CI measures the same band."""
    monkeypatch.delenv("CI", raising=False)


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


@pytest.mark.parametrize("value", ["1", "true", "True"])
def test_ci_scales_both_ceilings(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """A slower runner gets a scaled ceiling, not a different rule."""
    monkeypatch.setenv("CI", value)
    assert limits() == (1.0 * CI_SCALE, 5.0 * CI_SCALE)
    # What fails locally passes there; what is past the scaled ceiling fails.
    assert violation(set(), 1.01) is None
    assert "fast band limit of 3s" in str(violation(set(), CI_SCALE + 0.01))
    assert "medium band limit of 15s" in str(violation({"medium"}, 5 * CI_SCALE + 0.01))


@pytest.mark.parametrize("value", ["", "0", "false"])
def test_an_unset_or_falsey_ci_keeps_the_local_ceiling(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CI", value)
    assert limits() == (1.0, 5.0)


def test_the_top_bands_are_exempt_on_either_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI", "1")
    assert violation({"slow"}, 1000.0) is None
    assert violation({"weekly"}, 1000.0) is None
