"""Snapshot-bit bounds."""


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Count commands and distinguish the native constant that writes z."""
    tokens = program.split()
    return {"C": int(set(tokens) <= {"Z", "A", "$"}), "R": len(tokens)}
