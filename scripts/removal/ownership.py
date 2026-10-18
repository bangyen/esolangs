"""Which modules, files and documents a language owns.

The import-graph half of ``remove_language``: it works out which
implementation modules, scripts, test files and proof documents belong to
the language going, which of them surviving source still imports, and
which helper modules nothing else would name once they are gone.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).parents[2]
#: The files ``remove`` cuts the language's entries out of by itself; the
#: coupling guard does not count them for the same reason.

_EDITED = (
    "src/esolangs/registry/_table.py",
    "src/esolangs/languages/generators.py",
    "tests/support/samples.py",
    "tests/generators/test_wrap.py",
    "tests/proofs/test_execution_formulas.py",
    "tests/proofs/test_workspace_formulas.py",
    "tests/proofs/test_bands.py",
)


def _gone(module: str | None, modules: set[str]) -> bool:
    """Whether ``module`` is one of ``modules`` or inside one of them."""
    return module is not None and any(
        module == m or module.startswith(m + ".") for m in modules
    )


def _owned_scripts(lang: Language) -> list[Path]:
    """Return profiling and verification scripts owned by a canonical ID."""
    from esolangs.registry import LANGUAGES

    ids = {other.id for other in LANGUAGES.values()}
    return [
        path
        for path in (ROOT / "scripts").rglob("*.py")
        for prefix in ("profile_", "verify_")
        if path.stem.startswith(prefix)
        and _owner_id(path.stem.removeprefix(prefix), ids) == lang.id
    ]


def _module_path(module: str) -> Path | None:
    """Return a module's file, or its package directory, if it exists."""
    base = ROOT / "src" / module.replace(".", "/")
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base
    return None


def _module_of(path: Path) -> str:
    """Return the dotted module a ``src`` path or package directory holds."""
    relative = path.relative_to(ROOT / "src")
    return ".".join(relative.with_suffix("").parts).removesuffix(".__init__")


def _declaring_module(lang: Language) -> str | None:
    """Return the implementation module declaring ``lang``."""
    if lang.boolean is not None:
        name = lang.boolean.__module__
        if getattr(sys.modules.get(name), "LANGUAGE", None) is lang:
            return name
    for module_name, module in sorted(sys.modules.items()):
        if (
            module_name.startswith("esolangs.languages.")
            and getattr(module, "LANGUAGE", None) is lang
        ):
            return module_name
    return None


def _owned_evidence(name: str) -> set[Path]:
    """Return standalone proof documents cited exclusively by this language."""
    from docs.proof_status import aggregate_fragments

    from esolangs.registry import LANGUAGES, canonical_id

    packages = ROOT / "src/esolangs/languages"
    if not packages.is_dir():
        return set()
    doomed = next(
        (lang.id for lang in LANGUAGES.values() if lang.name == name),
        canonical_id(name),
    )
    # Rows are keyed by package id, not display name: removal works on the
    # tree under ROOT, whose packages need not be the installed registry's.
    generators = [
        (path.parent.name, path.parent.name)
        for path in sorted(packages.glob("*/language.toml"))
    ]
    data = aggregate_fragments(packages, generators)
    owners: dict[Path, set[str]] = {}
    proofs = (ROOT / "docs/proofs").resolve()
    for group in ("ledger", "audit"):
        for row in data[group]:
            relative = row.get("evidence", "").partition("#")[0]
            path = (ROOT / relative).resolve()
            if (
                path.is_relative_to(proofs)
                and path.name != "index.md"
                and path.is_file()
            ):
                owners.setdefault(path, set()).add(row["generator"])
    return {path for path, names in owners.items() if names == {doomed}}


def _owned_module_paths(lang: Language) -> tuple[set[str], set[Path]]:
    """Return owned implementation modules, keeping leaves separate."""
    modules = (
        {f"esolangs.languages.{lang.id}.interpreter"} if lang.interpreter else set()
    )
    declaring = _declaring_module(lang)
    if declaring:
        modules.add(declaring)
    package = ROOT / "src/esolangs/languages" / lang.id
    if package.is_dir():
        modules.add(f"esolangs.languages.{lang.id}.interpreter")
    paths = {path for module in modules if (path := _module_path(module))}
    init = package / "__init__.py"
    if init.is_file():
        paths.add(init)
    return modules, paths


def _python_files() -> list[str]:
    """Return every tracked or new Python file, repo-relative."""
    return subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()


def _imported(files: list[str]) -> dict[str, set[str]]:
    """Map each ``esolangs`` module to the files importing it, top level or not."""
    users: dict[str, set[str]] = {}
    for path in files:
        try:
            tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for module in _import_names(tree):
            if module.startswith(("esolangs.", "tests.")):
                users.setdefault(module, set()).add(path)
    return users


def _import_names(tree: ast.AST) -> set[str]:
    """Return every absolute module, and module.name, the tree imports."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def _within(path: str, doomed: set[Path]) -> bool:
    """Whether repo-relative ``path`` is one of, or inside one of, ``doomed``."""
    full = ROOT / path
    return any(full == d or d in full.parents for d in doomed)


def _is_test(path: str) -> bool:
    """Whether a repo-relative file belongs to either test tree."""
    return path.startswith("tests/") or (
        path.startswith("src/esolangs/languages/") and "/tests/" in path
    )


def _orphans(doomed: set[Path], users: dict[str, set[str]]) -> set[Path]:
    """Return the helper modules only ``doomed`` files import.

    A helper module the removal's own files alone import is dead code that
    nothing names once they are gone.  Public-named helpers count too (a
    helper named without the underscore), so a language whose helpers lack
    the underscore still leaves no dead module.  A helper no file imports at
    all is left alone: it was not the language's to begin with.
    """
    # The largest set whose every member only the doomed or each other
    # import: two helpers that import each other are dead together.
    found = {
        path
        for path in (ROOT / "src/esolangs").rglob("*.py")
        if not path.name.startswith("__")
        and not _is_test(path.relative_to(ROOT).as_posix())
        and not any(path == d or d in path.parents for d in doomed)
        and users.get(_module_of(path))
    }
    while True:
        gone = doomed | found
        outside = {
            path
            for path in found
            if not all(_within(user, gone) for user in users[_module_of(path)])
        }
        if not outside:
            return found
        found -= outside


def _drop_language_statement(path: Path) -> None:
    """Delete ``LANGUAGE = ...`` from a generator module kept for its helpers."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign | ast.AnnAssign) and any(
            isinstance(t, ast.Name) and t.id == "LANGUAGE"
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
        ):
            del lines[node.lineno - 1 : node.end_lineno]
            break
    path.write_text("".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def _owner_id(filename: str, ids: set[str]) -> str | None:
    """Return the longest language id owning ``filename`` at a name boundary.

    ``piet_plus_plus.toml`` is Piet++'s, not Piet's: the id must end the name
    or leave ``.``, ``_`` or ``-`` after it.
    """
    best: str | None = None
    for ident in ids:
        rest = filename[len(ident) :] if filename.startswith(ident) else None
        if rest is None or (rest and rest[0] not in "._-"):
            continue
        if best is None or len(ident) > len(best):
            best = ident
    return best


def _gone_modules(doomed: set[Path]) -> set[str]:
    """Return the importable names of the modules ``doomed`` would delete."""
    modules = {_module_of(p) for p in doomed if p.is_relative_to(ROOT / "src")}
    modules |= {
        ".".join(p.relative_to(ROOT).with_suffix("").parts)
        for p in doomed
        if p.is_relative_to(ROOT / "tests") and p.suffix == ".py"
    }
    return modules


def _dead_test_files(
    doomed: set[Path], gone_modules: set[str], users: dict[str, set[str]]
) -> set[Path]:
    """Return test files that import a gone module and nothing that survives.

    The owned prefixes name a language's module stems, not its submodules, so
    e.g. ``test_boolean_circuit_diagram_hcells.py`` (importing
    ``esolangs.languages.circuit_diagram.generator.hlayout``) is caught here;
    it cannot run once the module is gone.
    """
    candidates = {
        user
        for imported, importers in users.items()
        if _gone(imported, gone_modules)
        for user in importers
        if _is_test(user) and not _within(user, doomed)
    }
    dead: set[Path] = set()
    for path in candidates:
        if path in _EDITED:
            continue
        full = ROOT / path
        try:
            tree = ast.parse(full.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        found = {
            m
            for m in _import_names(tree)
            if m in {"esolangs", "tests"} or m.startswith(("esolangs.", "tests."))
        }
        if found and all(_gone(m, gone_modules) for m in found):
            dead.add(full)
    return dead


def _import_users(path: Path, users: dict[str, set[str]]) -> set[str]:
    """Return the files importing ``path``'s module or one of its submodules."""
    module = _module_of(path)
    return {
        user
        for imported, importers in users.items()
        if _gone(imported, {module})
        for user in importers
    }
