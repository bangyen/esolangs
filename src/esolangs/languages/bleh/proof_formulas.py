"""Command and written-state bounds for the short read alias."""


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Mark the statement-read construction."""
    return {"C": int("main:={" in program)}
