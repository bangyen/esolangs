"""Cost-band limits enforced by the pytest hook."""

import os

FAST_LIMIT = 1.0
MEDIUM_LIMIT = 5.0

# GitHub's runner is slower than the machine the bands were calibrated on, so
# the same test measures longer there and a locally-green band fails CI.  Over
# the nine tests that failed the run of 2026-09-15 the CI/local ratio was 1.76x
# to 2.52x (median 1.92x), so 3.0 clears every observed case with headroom.
# The alternative -- calibrating against a reference workload timed per run --
# only cut the drift of a deliberately loaded machine from 26% to 10%, which
# does not pay for a moving ceiling that no one can predict from a local run.
CI_SCALE = 3.0


def limits() -> tuple[float, float]:
    """Return the ``(fast, medium)`` ceilings for this machine.

    ``CI`` is set by GitHub Actions on every runner.
    """
    if os.environ.get("CI", "") in ("", "0", "false"):
        return FAST_LIMIT, MEDIUM_LIMIT
    return FAST_LIMIT * CI_SCALE, MEDIUM_LIMIT * CI_SCALE


def violation(markers: set[str], duration: float) -> str | None:
    """Return the cost-band violation for ``duration``, if any."""
    if markers & {"slow", "weekly"}:
        return None
    fast_limit, medium_limit = limits()
    band, limit, next_band = (
        ("medium", medium_limit, "slow")
        if "medium" in markers
        else ("fast", fast_limit, "medium")
    )
    if duration <= limit:
        return None
    return (
        f"{duration:.2f}s exceeds the {band} band limit of {limit:g}s; "
        f"optimize, delete, or mark this test {next_band}"
    )
