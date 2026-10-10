"""Compare committed documentation with a temporary regenerated copy."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate

ROOT = Path(__file__).parents[1]
GENERATED = (
    "README.md",
    "docs/proofs/index.md",
    "docs/roadmap.md",
    "docs/usage.md",
    "docs/limitations.md",
    "docs/CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/language_request.yml",
    "src/esolangs/tools/__init__.py",
)


def _manifest_is_stale() -> bool:
    """Return whether the committed examples manifest differs from its render.

    Only the manifest: regenerating every example program would make this
    check as slow as ``tests/scripts/test_examples.py``, which covers them.
    """
    manifest = generate.EXAMPLES / "MANIFEST.md"
    return manifest.read_text(encoding="utf-8") != (generate.boolean_manifest_text())


def main() -> int:
    """Return nonzero when the committed generated sections were stale."""
    before = {path: (ROOT / path).read_bytes() for path in GENERATED}
    with tempfile.TemporaryDirectory(prefix="generated-docs-") as directory:
        output_root = Path(directory)
        for path, content in before.items():
            target = output_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        result = generate.docs_main(output_root=output_root)
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
    if _manifest_is_stale():
        print(
            "examples/MANIFEST.md is stale; run python scripts/generate.py examples",
            file=sys.stderr,
        )
        return 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
