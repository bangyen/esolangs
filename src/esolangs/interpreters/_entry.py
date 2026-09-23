"""The shared ``python <file>`` entry point behind every interpreter.

Each interpreter keeps a two-line ``__main__`` block, because
``bundle_one.py`` keeps the target's one and a curl-fetched bundle has to
run standalone.  Its body moved here from 63 copies in nine variants, which
coverage's ``exclude_lines`` measured in none of them.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any, Literal

from esolangs.interpreters.io import IO

#: How ``run`` wants the source: the whole string, the lines with newlines
#: (``readlines()``), or without (``splitlines()``).  A grid language handed
#: kept newlines reads a column too many, so these are not interchangeable.
SourceShape = Literal["text", "keep", "strip"]


def script_main(
    run: Callable[[Any, IO], int | None], *, shape: SourceShape = "text"
) -> None:
    """Run the program file named by ``sys.argv[1]``, if one was given.

    A missing argument is a no-op; a non-``None`` return becomes the exit
    status (Container's halt).  Read as UTF-8, not the locale encoding.
    """
    if len(sys.argv) < 2:
        return
    with open(sys.argv[1], encoding="utf-8") as file:
        text = file.read()
    source: Any = text
    if shape == "keep":
        source = text.splitlines(keepends=True)
    elif shape == "strip":
        source = text.splitlines()
    code = run(source, IO())
    if code is not None:
        sys.exit(code)
