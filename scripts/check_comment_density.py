"""Fail any source file with fewer than two code lines per comment line.

A comment is worth keeping when it says something the code cannot -- a
number, a rejected alternative, an invariant.  Below two code lines per
comment line, what is there is nearly always restatement: the fact, then
the fact as a consequence, then the fact as a contrast.  Nobody reads all
of that, and a skipped comment is worth nothing.  Sixteen files sat at
1.0-2.0 in September 2026; rewriting each to one claim per comment lost no
number and put every one at 2.6-5.4.

Docstrings do not count on either side: they are the long-form home for an
argument a comment points at.  Files with fewer than ``MIN_COMMENTS``
comment lines are skipped, since a ratio over a handful of lines is noise.
"""

import io
import sys
import tokenize
from pathlib import Path

RATIO = 2.0
MIN_COMMENTS = 10

_SKIP = {
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
}


def density(source: str) -> tuple[int, int]:
    """Return ``(code_lines, comment_lines)``; docstring lines are neither."""
    code: set[int] = set()
    comments = 0
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            comments += 1
        elif tok.type not in _SKIP and not (
            tok.type == tokenize.STRING and tok.line.lstrip().startswith(('"""', "'''"))
        ):
            code.add(tok.start[0])
    return len(code), comments


def main(paths: list[str]) -> int:
    """Report every file under the ratio; exit 1 if any."""
    failed = 0
    for name in paths:
        code, comments = density(Path(name).read_text())
        if comments < MIN_COMMENTS or code / comments >= RATIO:
            continue
        failed += 1
        print(
            f"{name}: {code / comments:.1f} code lines per comment line "
            f"({code} code, {comments} comment); floor is {RATIO}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
