"""Start, check, or finish a new language.

    python scripts/new_language.py start "Name" --category tape_based
    python scripts/new_language.py check "Name"     # what is still missing
    python scripts/new_language.py finish "Name"    # regenerate, then verify

``start`` writes the interpreter, generator and test stubs.  ``check`` lists
every integration point the language still lacks, with the file and entry
to add; ``tests/scripts/test_new_language.py`` runs it over the registry,
so the list cannot drift from what the suite enforces.  ``finish``
regenerates every committed artifact and runs the full ``verify.py`` gate.
The bare ``"Name" --category ...`` form still means ``start``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import keyword
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).parents[1]
CATEGORIES = tuple(
    sorted(
        path.name
        for path in (ROOT / "src/esolangs/interpreters").iterdir()
        if path.is_dir() and (path / "__init__.py").exists()
    )
)
COMMANDS = ("start", "check", "finish")


def _slug(name: str) -> str:
    """Return the registry's id for ``name``, refused unless importable."""
    from esolangs.registry import canonical_id

    slug = canonical_id(name)
    if not slug.isidentifier() or keyword.iskeyword(slug):
        # ``class`` passed the old check and scaffolded an import line that
        # was a SyntaxError.
        raise ValueError(
            "name must produce a Python identifier beginning with a letter, "
            "and not a Python keyword"
        )
    return slug


_GENERATOR = '''"""Boolean program generator for {name}.

Describe the construction: how a node reads its input, branches, and
answers, and the size and build bound (O(T) for a decision tree).
"""

from esolangs.tools.helpers import _validate_truth_table


def {slug}(truth_table: str) -> str:
    """Build a {name} program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    raise NotImplementedError("{name} generator")
'''

_GENERATOR_TEST = '''"""Tests for the {name} Boolean generator."""

from itertools import product

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.{category}.{slug} import run
from esolangs.tools.{slug} import {slug}


@pytest.mark.parametrize("table", ["01", "10", "0001", "0110", "00010111"])
def test_every_row_prints_its_answer(table: str) -> None:
    n = len(table).bit_length() - 1
    program = {slug}(table)
    for row, bits in enumerate(product("01", repeat=n)):
        io = ScriptedIO("\\n".join(bits) + "\\n")
        run(program, io)
        assert io.getvalue() == table[row]
'''


def scaffold(name: str, category: str, *, generator: bool = True) -> list[Path]:
    """Create and return the interpreter, generator and test stubs."""
    slug = _slug(name)
    files = {
        ROOT / "src/esolangs/interpreters" / category / f"{slug}.py": (
            _interpreter_stub(name)
        ),
        ROOT / "tests" / "interpreters" / f"test_{slug}.py": (
            f'"""Tests for the {name} interpreter."""\n\n'
            f"from esolangs.interpreters.{category}.{slug} import run\n"
            "from esolangs.interpreters.io import ScriptedIO\n\n\n"
            "def test_placeholder_increment_and_write() -> None:\n"
            "    io = ScriptedIO()\n"
            '    run("+.", io)\n'
            '    assert io.getvalue() == "\\x01"\n'
        ),
    }
    if generator:
        fields = {"name": name, "slug": slug, "category": category}
        files[ROOT / "src" / "esolangs" / "tools" / f"{slug}.py"] = _GENERATOR.format(
            **fields
        )
        files[ROOT / "tests" / "tools" / f"test_boolean_{slug}.py"] = (
            _GENERATOR_TEST.format(**fields)
        )
    collisions = [path for path in files if path.exists()]
    if collisions:
        joined = ", ".join(str(path.relative_to(ROOT)) for path in collisions)
        raise FileExistsError(f"refusing to overwrite {joined}")
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return list(files)


def _interpreter_stub(name: str) -> str:
    template = (ROOT / "src/esolangs/interpreters/_template.py").read_text()
    return template.replace(
        '"""Template for a new esolang interpreter.',
        f'"""Interpreter for {name}.',
        1,
    )


@dataclass(frozen=True)
class Gap:
    """One missing integration point: where it goes and what to put there."""

    where: str
    fix: str


def _tests_module(module: str, attr: str) -> object:
    """Read ``attr`` from ``tests.<module>``, which needs the repo on the path."""
    sys.path.insert(0, str(ROOT))
    try:
        return getattr(importlib.import_module(f"tests.{module}"), attr)
    finally:
        sys.path.remove(str(ROOT))


def _unregistered(name: str, slug: str) -> Gap:
    found = sorted((ROOT / "src/esolangs/interpreters").glob(f"*/{slug}.py"))
    module = f"{found[0].parent.name}.{slug}" if found else f"<category>.{slug}"
    generator = ""
    if (ROOT / f"src/esolangs/tools/{slug}.py").exists():
        generator = f"boolean=_boolean.{slug}, "
    return Gap(
        "src/esolangs/registry/_table.py",
        f'add "{name}": Language("{name}", "{module}", {generator}id="{slug}"), '
        "plus split=True if the interpreter takes lines",
    )


def _common_gaps(name: str, module: str) -> list[Gap]:
    """List the steps every language needs, generator or not."""
    gaps = []
    base = ROOT / "src/esolangs/interpreters" / module.replace(".", "/")
    if not (base.with_suffix(".py").exists() or (base / "__init__.py").exists()):
        gaps.append(Gap(f"{base.relative_to(ROOT)}.py", "write the interpreter"))
    needle = f"esolangs.interpreters.{module}"
    if not any(
        needle in path.read_text(encoding="utf-8")
        for path in (ROOT / "tests").rglob("*.py")
    ):
        gaps.append(Gap("tests/interpreters/", f"add tests importing {needle}"))
    if name not in _tests_module("samples", "SAMPLES"):
        gaps.append(
            Gap(
                "tests/samples.py",
                f'add "{name}": (<tiny program>, <stdin>) to SAMPLES; the VM '
                "protocol and debugger tests step it",
            )
        )
    curation = json.loads((ROOT / "tests/fixtures/curation.json").read_text())
    if name not in curation["languages"]:
        gaps.append(
            Gap(
                "tests/fixtures/curation.json",
                f'add "{name}": {{"backlinks": <wiki "What links here" count>, '
                '"route": "fame" | "first implementation"} (see '
                "docs/limitations.md#curation)",
            )
        )
    return gaps


def _generator_gaps(lang: Language) -> list[Gap]:
    """List the steps a language with a Boolean generator needs."""
    from esolangs import tools
    from esolangs.tools.balance import BALANCERS
    from esolangs.tools.examples import BOOLEAN_EXAMPLES
    from esolangs.tools.wrap import WRAPPERS, takes_width

    assert lang.boolean is not None
    gen = lang.boolean.__name__
    gaps = []
    if gen not in tools.__all__:
        gaps.append(
            Gap(
                "src/esolangs/tools/__init__.py",
                f'add `from esolangs.tools.{gen} import {gen}` and "{gen}" to __all__',
            )
        )
    if not any(ex.interpreter == lang.interpreter for ex in BOOLEAN_EXAMPLES.values()):
        stem = lang.name.lower().replace(" ", "-")
        gaps.append(
            Gap(
                "src/esolangs/tools/examples.py",
                f'add "{stem}": _reader(b.{gen}, "{lang.interpreter}") to the '
                "reading examples (_embedded for a template)",
            )
        )
    width = takes_width(lang.boolean)
    exceptions = _tests_module("tools.test_wrap", "WIDTH_EXCEPTIONS")
    if not width and lang.id not in WRAPPERS and lang.id not in exceptions:
        gaps.append(
            Gap(
                "src/esolangs/tools/wrap.py",
                f'add "{lang.id}": wrap_chars (or the wrapper its syntax needs) to '
                "WRAPPERS, take a width parameter, or say why it cannot in "
                "WIDTH_EXCEPTIONS in tests/tools/test_wrap.py",
            )
        )
    if width and lang.id not in BALANCERS:
        gaps.append(
            Gap("src/esolangs/tools/balance.py", f'add "{lang.id}" to BALANCERS')
        )
    return gaps + _ledger_gaps(lang.name)


def _ledger_gaps(name: str) -> list[Gap]:
    """List the ledger row and the formula tests its stated bounds need."""
    data = json.loads((ROOT / "src/esolangs/proof_status.json").read_text())
    row = next((row for row in data["ledger"] if row["generator"] == name), None)
    if row is None:
        return [
            Gap(
                "src/esolangs/proof_status.json",
                f'add a "ledger" row {{"generator": "{name}", "labels": ["tree"], '
                '"qualification", "scaling", "execution", "workspace", "evidence": '
                '"docs/proofs/index.md#generator-ledger"}; copy a row with the '
                "same construction and see Symbols in docs/proofs/index.md",
            )
        ]
    if not row["execution"].split(": ", 1)[-1].startswith(("worst ", "at most ")):
        return []
    gaps = []
    for cell in ("execution", "workspace"):
        stated = row[cell].split(": ", 1)[-1]
        table = f"test_{cell}_formulas"
        if cell == "workspace" and "bits" not in stated:
            continue
        if name not in _tests_module(f"proofs.{table}", "FORMULAS"):
            gaps.append(
                Gap(
                    f"tests/proofs/{table}.py",
                    f'add "{name}": (lambda n, p: ..., exact, (lo, hi)) to '
                    f"FORMULAS, encoding the ledger's {cell} cell: {stated}",
                )
            )
    return gaps


def check(name: str) -> list[Gap]:
    """Return every integration point ``name`` still lacks, in order."""
    from esolangs.registry import LANGUAGES, canonical_id

    lang = LANGUAGES.get(name)
    if lang is None:
        return [_unregistered(name, canonical_id(name))]
    gaps = _common_gaps(name, lang.interpreter or "")
    if lang.boolean is not None:
        gaps += _generator_gaps(lang)
    return gaps


def finish(name: str) -> int:
    """Regenerate every committed artifact, then run the full gate."""
    gaps = check(name)
    if gaps:
        _report(name, gaps)
        return 1
    python = [sys.executable]
    for cmd in (
        [*python, "scripts/generate.py", "examples"],
        [*python, "scripts/generate.py", "docs"],
        [*python, "scripts/check_generator_sizes.py", "--update"],
        [*python, "scripts/verify.py"],
    ):
        print("+", " ".join(cmd[1:]), flush=True)
        if subprocess.run(cmd, cwd=ROOT, check=False).returncode:
            return 1
    return 0


def _report(name: str, gaps: list[Gap]) -> None:
    print(f"{name}: {len(gaps)} step(s) left")
    for gap in gaps:
        print(f"- {gap.where}: {gap.fix}")
    print(f"rerun: python scripts/new_language.py check {name!r}")


def main(argv: list[str] | None = None) -> int:
    """Dispatch ``start``, ``check`` or ``finish``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        argv.insert(0, "start")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="write the stubs")
    start.add_argument("name")
    start.add_argument("--category", choices=CATEGORIES, required=True)
    start.add_argument(
        "--interpreter-only",
        action="store_true",
        help="no generator: only for a famous language whose spec precludes one",
    )
    for command in ("check", "finish"):
        sub.add_parser(command).add_argument("name")
    args = parser.parse_args(argv)
    if args.command == "check":
        gaps = check(args.name)
        if gaps:
            _report(args.name, gaps)
            return 1
        print(
            f"{args.name}: integrated; next: "
            f"python scripts/new_language.py finish {args.name!r}"
        )
        return 0
    if args.command == "finish":
        return finish(args.name)
    try:
        paths = scaffold(args.name, args.category, generator=not args.interpreter_only)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    for path in paths:
        print(f"created {path.relative_to(ROOT)}")
    print(
        "next: implement the interpreter (see docs/CONTRIBUTING.md#interpreter-"
        "conventions) and generator, then run "
        f"`python scripts/new_language.py check {args.name!r}` for the rest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
