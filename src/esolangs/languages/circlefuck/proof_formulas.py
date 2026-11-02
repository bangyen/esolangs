"""Executed command and written-state bounds."""

from esolangs.languages.circlefuck.interpreter import parse


def execution(n: int, p: str) -> int:
    """The indexed path, plus the reader's worst row (every bit one)."""
    cells = parse(p)
    if n < 3:
        return (2 * n + 13) * (1 << n) + 94 * n + 89 + 2 * sum(cells[1 : n + 1])
    # Old reader: 98n+2S; batch: 72n+143+2C. The backend is unchanged.
    return (2 * n + 13) * (1 << n) + 68 * n + 232 + 2 * cells[n + 1]


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
