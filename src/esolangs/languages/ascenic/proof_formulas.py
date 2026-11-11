"""Snapshot-bit bounds."""


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Identify the constant reader and its optional LT flag."""
    lines = program.splitlines()
    constant = len(lines) == 2 * n + 1
    return {"C": int(constant), "S": int(constant and lines[-2].count("A") == 13)}
