"""Cost-band limits enforced by the pytest hook."""

FAST_LIMIT = 1.0
MEDIUM_LIMIT = 5.0


def violation(markers: set[str], duration: float) -> str | None:
    """Return the cost-band violation for ``duration``, if any."""
    if markers & {"slow", "weekly"}:
        return None
    band, limit, next_band = (
        ("medium", MEDIUM_LIMIT, "slow")
        if "medium" in markers
        else ("fast", FAST_LIMIT, "medium")
    )
    if duration <= limit:
        return None
    return (
        f"{duration:.2f}s exceeds the {band} band limit of {limit:g}s; "
        f"optimize, delete, or mark this test {next_band}"
    )
