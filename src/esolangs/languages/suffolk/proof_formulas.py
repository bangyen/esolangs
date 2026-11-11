"""Executed command bounds."""


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Count the prefix through the first read, where the next pass sees EOF."""
    return {"R": program.index(",") + 1}
