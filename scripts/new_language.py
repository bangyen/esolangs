"""Create the interpreter and test stubs for a new language."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
CATEGORIES = (
    "grid_based",
    "other",
    "queue_based",
    "register_based",
    "stack_based",
    "tape_based",
)


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    if not slug or slug[0].isdigit():
        raise ValueError(
            "name must produce a Python identifier beginning with a letter"
        )
    return slug


def scaffold(name: str, category: str) -> tuple[Path, Path]:
    """Create and return the interpreter and test paths."""
    slug = _slug(name)
    source = ROOT / "src" / "esolangs" / "interpreters" / category / f"{slug}.py"
    test = ROOT / "tests" / "interpreters" / f"test_{slug}.py"
    collisions = [path for path in (source, test) if path.exists()]
    if collisions:
        joined = ", ".join(str(path.relative_to(ROOT)) for path in collisions)
        raise FileExistsError(f"refusing to overwrite {joined}")
    template = (ROOT / "src" / "esolangs" / "interpreters" / "_template.py").read_text()
    template = template.replace(
        '"""Template for a new esolang interpreter.',
        f'"""Interpreter for {name}.',
        1,
    )
    source.parent.mkdir(parents=True, exist_ok=True)
    test.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(template)
    test.write_text(
        f'"""Tests for the {name} interpreter."""\n\n'
        f"from esolangs.interpreters.{category}.{slug} import run\n"
        "from esolangs.interpreters.io import ScriptedIO\n\n\n"
        "def test_placeholder_increment_and_write() -> None:\n"
        "    io = ScriptedIO()\n"
        '    run("+.", io)\n'
        '    assert io.getvalue() == "\\x01"\n'
    )
    return source, test


def main(argv: list[str] | None = None) -> int:
    """Create stubs and print the remaining integration checklist."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--category", choices=CATEGORIES, required=True)
    args = parser.parse_args(argv)
    try:
        source, test = scaffold(args.name, args.category)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    print(f"created {source.relative_to(ROOT)}")
    print(f"created {test.relative_to(ROOT)}")
    print(
        "remaining: implement semantics; add generator and registry entry; "
        "add example metadata"
    )
    print("then run: uv run python scripts/generate.py docs && just test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
