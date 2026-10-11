"""Fail any source file with fewer than two code lines per line of prose.

Prose is every comment line plus every docstring line past the first
paragraph.  A docstring's first paragraph is the contract and is free; what
follows it is commentary and counts exactly as a ``#`` comment would, so
moving a note from one to the other changes nothing.  Prose is worth
keeping when it says something the code cannot -- a number, a rejected
alternative, an invariant.  Below two code lines per prose line, what is
there is nearly always restatement, and a skipped note is worth nothing.

Files with fewer than ``MIN_PROSE`` prose lines are skipped, since a ratio
over a handful of lines is noise.
"""

import io
import sys
import tokenize
from pathlib import Path

RATIO = 2.0
MIN_PROSE = 10

_SKIP = {
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
}


def _docstring_body(text: str) -> int:
    """Return how many lines of a docstring follow its first paragraph."""
    lines = [line.strip() for line in text.strip("\"'").strip().splitlines()]
    try:
        first_gap = lines.index("")
    except ValueError:
        return 0
    return sum(1 for line in lines[first_gap:] if line)


def density(source: str) -> tuple[int, int]:
    """Return ``(code_lines, prose_lines)`` for one file."""
    code: set[int] = set()
    prose = 0
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            prose += 1
        elif tok.type == tokenize.STRING and tok.line.lstrip().startswith(
            ('"""', "'''")
        ):
            prose += _docstring_body(tok.string)
        elif tok.type not in _SKIP:
            code.add(tok.start[0])
    return len(code), prose


def main(paths: list[str]) -> int:
    """Report every file under the ratio; exit 1 if any."""
    failed = 0
    for name in paths:
        code, prose = density(Path(name).read_text())
        if prose < MIN_PROSE or code / prose >= RATIO:
            continue
        failed += 1
        print(
            f"{name}: {code / prose:.1f} code lines per prose line "
            f"({code} code, {prose} prose); floor is {RATIO}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
