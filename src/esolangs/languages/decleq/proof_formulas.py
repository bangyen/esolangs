"""Executed command and snapshot-bit bounds."""

from esolangs.runtime.memory import parse_int_memory


def _bits(value: int) -> int:
    return (value.bit_length() or 1) + (value < 0)


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Measure the initial image and identify the native constant reader."""
    cells = parse_int_memory(program)
    return {"B": sum(map(_bits, cells)), "R": len(cells), "C": int(cells[0] == -1)}
