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


def test_a_starved_test_is_excused_but_a_slow_one_is_not() -> None:
    """Wall time past the band is contention only if the work fit the band."""
    # 1.15s wall for 0.30s of work: descheduled, not slow.
    assert violation(set(), 1.15, 0.30) is None
    # The same wall time for work that itself blew the band is a real overrun.
    assert "fast band limit of 1s" in str(violation(set(), 1.15, 1.02))


def test_the_excuse_runs_out_past_the_scaled_ceiling() -> None:
    """No amount of starvation explains three times the band."""
    assert violation(set(), 1.0 * CI_SCALE + 0.01, 0.01) is not None


def test_cpu_time_can_only_excuse_an_overrun_never_cause_one() -> None:
    """``process_time`` sums threads, so a pool reads a multiple of its wall.

    A rule that failed on CPU alone would fail tests sitting well inside
    their band, which is why the check is consulted only after the wall
    time is already past the ceiling.
    """
    assert violation(set(), 0.5, 4.0) is None
    assert violation({"medium"}, 2.0, 12.0) is None


def test_an_unmeasured_call_keeps_the_plain_wall_rule() -> None:
    """The caller may not have timed the CPU; then the ceiling is unchanged."""
    assert violation(set(), 1.01, None) is not None
    assert violation(set(), 1.01) is not None
