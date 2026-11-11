"""Executed command and written-state bounds."""

from esolangs.languages.circlefuck.interpreter import parse


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Read the individual or batched reader tally from the initial tape."""
    cells = parse(program)
    return {"U": sum(cells[1 : n + 1]) if n < 3 else cells[n + 1]}


def workspace(n: int, p: str) -> int:
    """Initial tape peak, instruction/data cursors, input cursor and halt flag."""
    cells = parse(p)
    # On bit inputs each writable bank loses five bits before an index can
    # grow; the initial tape remains the peak, including all bracket bytes.
    # Count actual bytes: the old expression missed extra index-digit code.
    return (
        sum(max(1, cell.bit_length()) for cell in cells)
        + (len(cells) - 1).bit_length()
        + cells.index(ord("@")).bit_length()
        + n.bit_length()
        + 1
    )
