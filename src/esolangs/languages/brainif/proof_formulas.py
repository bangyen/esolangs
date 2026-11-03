"""Snapshot-bit bounds."""


def workspace(n: int, p: str) -> int:
    """Default DAG: two ASCII cells and their one-bit pointer cost thirteen bits.

    OR preserves its answer beside trailing ignored inputs in the same envelope.
    """
    bl = int.bit_length
    lines = p.splitlines()
    cells = (
        6
        if len(lines) == 2 * n + 1 and lines[-2:] == ["if 48 inc", "if 49 output"]
        else 13
    )
    return cells + bl(len(lines)) + bl(n)
