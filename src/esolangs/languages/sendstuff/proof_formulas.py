"""Snapshot-bit bounds."""


def _frame_indices(n: int) -> int:
    """Total index widths over the largest parser shapes at each depth."""

    def nodes(j: int) -> int:
        """Most parser nodes at depth j: 4 per unequal-halves subtable, 1 else."""
        if j == n:
            return 4
        s, p = 1 << (n - j), 1 << j
        b = min(p, (1 << s) - (1 << (s // 2)))
        return 4 * b + min(p - b, 1 << (s // 2))

    later = nodes(n)
    bits = 0
    for depth in range(n - 1, -1, -1):
        later += nodes(depth)
        bits += (later - 3).bit_length()
    return bits


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Identify unary readers or measure the generic frame index widths."""
    terms = execution_terms(n, program)
    return terms | {"W": 0 if terms["U"] else _frame_indices(n)}


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Identify unary readers and count the sends beyond the plain reader."""
    text = "".join(program.split())
    if not text.startswith(">(Input>"):
        return {"U": 0, "R": 0}
    if "Constant" in text:
        return {"U": 1, "R": 1}
    return {"U": 1, "R": 2 * int("Divide48" in text)}
