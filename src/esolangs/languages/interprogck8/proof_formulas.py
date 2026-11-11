"""Snapshot-bit bound, R the program's lines."""


def _lines(program: str) -> int:
    return len(program.split("\n")) - program.endswith("\n")


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Count source lines and identify constants without a slot frame."""
    return {"R": _lines(program), "C": int(program.startswith("u\n"))}
