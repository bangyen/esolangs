"""Bundle one interpreter into a single self-contained file.

Every interpreter imports two shared modules, ``esolangs.exceptions`` and
``esolangs.interpreters.io``, which means a raw ``curl`` of a single source
file cannot run standalone.  This script inlines those modules (and any
interpreter the target imports, e.g. Factor's brainfuck) into one file that
runs exactly like ``python -m esolangs.interpreters.<category>.<lang>``:

    python scripts/bundle_one.py <language>

The output file is ``esolangs_<lang>.py`` in the current directory and is
run with ``python esolangs_<lang>.py program.txt``.

``scripts/install_one.sh`` wraps this script in a one-line pipe that fetches
everything from GitHub, so someone can grab a single interpreter without
cloning the repository or installing the package:

    curl -fsSL https://raw.githubusercontent.com/bangyen/esolangs/main/scripts/install_one.sh
        | sh -s brainfuck

Source files are read from the local checkout by default, or from a ``--base``
URL (as the installer does).  Interpreter-to-interpreter imports are resolved
recursively and aliased, so bundled languages behave identically to their
package versions.
"""

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "esolangs"

_SYMPY = re.compile(r"^\s*(?:import sympy|from sympy)", re.M)


class Source:
    """Read source files from the repo or from a raw GitHub base URL."""

    def __init__(self, base: str | None) -> None:
        """Use the local checkout unless a ``base`` URL is given."""
        self._base = base

    def get(self, rel: str) -> str:
        """Return the text of the file at ``rel`` under ``src/esolangs``."""
        if self._base is None:
            return (SRC / rel).read_text()
        import urllib.request

        url = self._base.rstrip("/") + "/src/esolangs/" + rel
        with urllib.request.urlopen(url) as response:
            text: str = response.read().decode()
        return text


def _line_span(node: ast.stmt) -> range:
    """Return the 1-based line numbers ``node`` occupies, end inclusive.

    ``end_lineno`` is ``int | None`` because synthesised nodes carry no
    position, but every node here comes from ``ast.parse``, which always
    sets it.
    """
    assert node.end_lineno is not None
    return range(node.lineno, node.end_lineno + 1)


def _is_main(node: ast.stmt) -> bool:
    """Return whether ``node`` is an ``if __name__ == "__main__":`` block."""
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )


def _drop_lines(src: str, drop: set[int]) -> str:
    """Return ``src`` with the given 1-based line numbers removed."""
    return "".join(
        line for i, line in enumerate(src.splitlines(keepends=True), 1) if i not in drop
    )


def _parse_registry(source: Source) -> dict[str, str]:
    """Map each display name to its interpreter module path.

    ``registry.py`` is parsed with ``ast`` (never executed), so the mapping
    works against a raw download where the ``esolangs`` package cannot be
    imported.  The interpreter argument is either the ``interpreter=`` keyword
    or the third positional ``Language(name, generator, interpreter, ...)``
    slot.
    """
    tree = ast.parse(source.get("registry.py"))
    langs: dict[str, str] = {}
    for node in tree.body:
        targets: list[ast.expr]
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if not (
            value is not None
            and isinstance(value, ast.Dict)
            and any(isinstance(t, ast.Name) and t.id == "LANGUAGES" for t in targets)
        ):
            continue
        for key, entry in zip(value.keys, value.values, strict=True):
            if not (isinstance(key, ast.Constant) and isinstance(entry, ast.Call)):
                continue
            interpreter: str | None = None
            for kw in entry.keywords:
                if (
                    kw.arg == "interpreter"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    interpreter = kw.value.value
            if (
                interpreter is None
                and len(entry.args) > 2
                and isinstance(entry.args[2], ast.Constant)
                and isinstance(entry.args[2].value, str)
            ):
                interpreter = entry.args[2].value
            if interpreter and isinstance(key.value, str):
                langs[key.value] = interpreter
    return langs


def _top_level_names(src: str) -> list[str]:
    """Return the top-level function and class names in a module's source."""
    tree = ast.parse(src)
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]


class _ModuleInfo:
    """What a module needs from, and contributes to, the bundle."""

    def __init__(self) -> None:
        self.doc = ""
        self.futures: list[str] = []
        self.requires_sympy = False
        self.esolangs: list[tuple[str, list[tuple[str, str | None]]]] = []
        self.relative: list[tuple[str, str | None]] = []
        self.body = ""


def _process_module(src: str, *, keep_main: bool) -> _ModuleInfo:
    """Split a module into a bundle-able body and its esolangs dependencies."""
    info = _ModuleInfo()
    info.requires_sympy = _SYMPY.search(src) is not None
    tree = ast.parse(src)
    drop: set[int] = set()

    if tree.body and isinstance(tree.body[0], ast.Expr):
        first = tree.body[0]
        if isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            info.doc = first.value.value
            drop.update(_line_span(first))

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                info.futures.append(ast.unparse(node))
                drop.update(_line_span(node))
            elif node.module and node.module.startswith("esolangs."):
                info.esolangs.append(
                    (node.module, [(a.name, a.asname) for a in node.names])
                )
                drop.update(_line_span(node))
            elif node.level:
                info.relative.extend((a.name, a.asname) for a in node.names)
                drop.update(_line_span(node))
        elif _is_main(node) and not keep_main:
            drop.update(_line_span(node))

    info.body = _drop_lines(src, drop).rstrip()
    return info


def _inline_deps(
    source: Source,
    rel: str,
    seen: set[str],
    parts: list[str],
    futures: set[str],
    requires_sympy: set[str],
    *,
    keep_main: bool,
) -> _ModuleInfo:
    """Inline ``rel`` and its esolangs dependencies into ``parts``.

    Dependencies are emitted first (their bodies feed the module that imports
    them), then the alias bindings that let the importing module reach the
    inlined names, then the module's own body.
    """
    if rel in seen:
        return _ModuleInfo()
    seen.add(rel)

    info = _process_module(source.get(rel), keep_main=keep_main)

    for dotted, _aliases in info.esolangs:
        _inline_deps(
            source,
            dotted[len("esolangs.") :].replace(".", "/") + ".py",
            seen,
            parts,
            futures,
            requires_sympy,
            keep_main=False,
        )
    for name, _asname in info.relative:
        _inline_deps(
            source,
            str(Path(rel).parent / f"{name}.py"),
            seen,
            parts,
            futures,
            requires_sympy,
            keep_main=False,
        )

    parts.append(f"# --- inlined from esolangs/{rel} ---")
    for _dotted, aliases in info.esolangs:
        for name, asname in aliases:
            if asname and asname != name:
                parts.append(f"{asname} = {name}")
    for name, _asname in info.relative:
        sibling = str(Path(rel).parent / f"{name}.py")
        names = _top_level_names(source.get(sibling))
        if names:
            parts.append("from types import SimpleNamespace as _Namespace")
            parts.append(f"{name} = _Namespace({', '.join(f'{n}={n}' for n in names)})")
    parts.append(info.body)
    futures.update(info.futures)
    if info.requires_sympy:
        requires_sympy.add(rel)
    return info


def _resolve(language: str, langs: dict[str, str]) -> str:
    """Return the interpreter module path, matching case-insensitively."""
    if language in langs:
        return langs[language]
    for name, module in langs.items():
        if name.lower() == language.lower():
            return module
    raise KeyError(language)


def bundle(language: str, source: Source, out: Path | None) -> Path:
    """Write the self-contained interpreter bundle and return its path."""
    langs = _parse_registry(source)
    module = _resolve(language, langs)
    stem = module.rsplit(".", 1)[-1]
    rel = f"interpreters/{module.replace('.', '/')}.py"

    parts: list[str] = []
    futures: set[str] = set()
    requires_sympy: set[str] = set()
    info = _inline_deps(
        source,
        rel,
        set(),
        parts,
        futures,
        requires_sympy,
        keep_main=True,
    )

    if out is None:
        out = Path.cwd() / f"esolangs_{stem}.py"

    header = [
        "#!/usr/bin/env python3",
        f'"""Self-contained interpreter for {language}.',
        "",
        "Bundled from the esolangs repository",
        "(https://github.com/bangyen/esolangs) by scripts/bundle_one.py.",
        "The interpreter and the shared esolangs.exceptions and",
        "esolangs.interpreters.io modules are inlined, so this file runs",
        "without cloning the repo or installing the package.",
        "",
        f"Usage:  python {out.name} program.txt",
        '"""',
    ]
    if futures:
        header.append("")
        header.extend(sorted(futures))
    if requires_sympy:
        header.append("")
        header.append("# Requires: pip install sympy")
    if info.doc:
        header.append("")
        header.append("# Original module docstring:")
        header.extend(f"# {line}" for line in info.doc.splitlines())
    header.append("")

    text = "\n".join(header) + "\n" + "\n\n".join(part for part in parts if part) + "\n"
    compile(text, out.name, "exec")
    out.write_text(text)
    return out


def main() -> int:
    """Run the bundler from the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("language", help="display name of the language to bundle")
    parser.add_argument(
        "--out", type=Path, help="output file (default esolangs_<lang>.py)"
    )
    parser.add_argument(
        "--base",
        default=None,
        help="raw GitHub base URL to fetch from instead of the local checkout",
    )
    args = parser.parse_args()

    source = Source(args.base)
    try:
        out = bundle(args.language, source, args.out)
    except KeyError:
        print(f"unknown language: {args.language}", file=sys.stderr)
        return 2
    print(f"wrote {out}")
    print(f"run it with:  python {out.name} program.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
