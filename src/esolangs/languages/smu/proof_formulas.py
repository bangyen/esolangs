"""Snapshot-bit bounds."""


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Identify the constant route and its empty-name store."""
    return {"C": int("".join(program.split()).startswith("k((())=())km"))}
