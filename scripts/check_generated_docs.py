"""Regenerate committed documentation and fail when it changed."""

from __future__ import annotations

import sys
from pathlib import Path

from esolangs.tools import _generate_docs

ROOT = Path(__file__).parents[1]
GENERATED = (
    "README.md",
    "docs/usage.md",
    "docs/CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/language_request.yml",
)


def main() -> int:
    """Return nonzero when the committed generated sections were stale."""
    before = {path: (ROOT / path).read_bytes() for path in GENERATED}
    result = _generate_docs.main()
    changed = [
        path
        for path, content in before.items()
        if (ROOT / path).read_bytes() != content
    ]
    if changed:
        print(
            "generated documentation was stale; regenerated: " + ", ".join(changed),
            file=sys.stderr,
        )
        return 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
