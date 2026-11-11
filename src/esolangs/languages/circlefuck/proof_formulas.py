"""Executed command and written-state bounds."""

from esolangs.languages.circlefuck.interpreter import parse


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Read the individual or batched reader tally from the initial tape."""
    cells = parse(program)
    return {"U": sum(cells[1 : n + 1]) if n < 3 else cells[n + 1]}


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Measure the initial tape, its extent and the data origin."""
    cells = parse(program)
    return {
        "B": sum(max(1, cell.bit_length()) for cell in cells),
        "R": len(cells),
        "A": cells.index(ord("@")),
    }
