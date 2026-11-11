"""Executed command and snapshot-bit bounds."""

from esolangs.runtime.memory import parse_int_memory


def _native(n: int, p: str) -> list[int]:
    cells = parse_int_memory(p)
    return cells if len(cells) == 4 * (n + 1) + 2 and cells[0] == 4 * (n + 1) else []


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Identify the native constant memory layout."""
    return {"C": int(bool(_native(n, program)))}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Measure the sparse initial image of a direct constant."""
    cells = _native(n, program)
    initial = sum(
        max(1, address.bit_length()) + value.bit_length() + (value < 0)
        for address, value in enumerate(cells)
        if value
    )
    return {"C": int(bool(cells)), "A": initial}
