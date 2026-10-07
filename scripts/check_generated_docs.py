"""Compare committed documentation with a temporary regenerated copy."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import generate_docs

ROOT = Path(__file__).parents[1]
GENERATED = (
    "README.md",
    "docs/proofs/index.md",
    "docs/roadmap.md",
    "docs/usage.md",
    "docs/CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/language_request.yml",
)


def main() -> int:
    """Return nonzero when the committed generated sections were stale."""
    before = {path: (ROOT / path).read_bytes() for path in GENERATED}
    with tempfile.TemporaryDirectory(prefix="generated-docs-") as directory:
        output_root = Path(directory)
        for path, content in before.items():
            target = output_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        result = generate_docs.main(output_root=output_root)
        changed = [
            path
            for path, content in before.items()
            if (output_root / path).read_bytes() != content
        ]
    if changed:
        print(
            "generated documentation is stale; run python scripts/generate.py docs: "
            + ", ".join(changed),
            file=sys.stderr,
        )
        return 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
