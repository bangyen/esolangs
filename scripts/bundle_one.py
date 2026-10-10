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
import functools
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

    def __eq__(self, other: object) -> bool:
        """Two sources reading the same base are the same source."""
        return isinstance(other, Source) and other._base == self._base

    def __hash__(self) -> int:
        """Hash by base, so the parsed registry is cached per base."""
        return hash(self._base)

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


def _languages_tables(tree: ast.Module) -> list[ast.Dict]:
    """Return registry dicts, including ``CLASSICS`` from older raw sources."""
    tables: list[ast.Dict] = []
    for node in tree.body:
        targets: list[ast.expr]
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if isinstance(value, ast.Dict) and any(
            isinstance(t, ast.Name) and t.id in {"LANGUAGES", "CLASSICS"}
            for t in targets
        ):
            tables.append(value)
    return tables


def _interpreter_of(entry: ast.expr) -> str | None:
    """Return the interpreter path a ``Language(...)`` call names, if any.

    The argument is either the ``interpreter=`` keyword or the second
    positional slot.
    """
    if not isinstance(entry, ast.Call):
        return None
    interpreter: str | None = None
    for kw in entry.keywords:
        if (
            kw.arg == "interpreter"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            interpreter = kw.value.value
    if interpreter is not None:
        return interpreter
    if (
        len(entry.args) > 1
        and isinstance(entry.args[1], ast.Constant)
        and isinstance(entry.args[1].value, str)
    ):
        return entry.args[1].value
    return None


def _generator_modules(source: Source) -> list[str]:
    """Return the source of each module ``tools/__init__.py`` imports from."""
    modules = sorted(
        {
            node.module.split(".", 2)[2]
            for node in ast.parse(source.get("tools/__init__.py")).body
            if isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("esolangs.tools.")
        }
    )
    texts = []
    for module in modules:
        for rel in (f"tools/{module}.py", f"tools/{module}/__init__.py"):
            try:
                text = source.get(rel)
            except (OSError, ValueError):
                continue
            # The declaration closes the module; parsing only it is what
            # keeps a bundle from parsing every generator in full.
            start = text.find("\nLANGUAGE = ")
            if start >= 0:
                texts.append(text[start:])
            break
    return texts


@functools.cache
def _parse_registry(source: Source) -> dict[str, str]:
    """Map each display name to its interpreter module path.

    Sources are parsed with ``ast`` (never executed), so the mapping works
    against a raw download where the ``esolangs`` package cannot be
    imported.  A generator module declares ``LANGUAGE = Language(...)``;
    ``registry/_table.py`` lists the rest, and in older sources every
    language as a dict keyed by display name.
    """
    table = ast.parse(source.get("registry/_table.py"))
    langs: dict[str, str] = {}
    for dictionary in _languages_tables(table):
        for key, entry in zip(dictionary.keys, dictionary.values, strict=True):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            interpreter = _interpreter_of(entry)
            if interpreter:
                langs[key.value] = interpreter
    if langs:
        return langs
    for tree in (table, *map(ast.parse, _generator_modules(source))):
        for call in ast.walk(tree):
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "Language"
                and call.args
                and isinstance(call.args[0], ast.Constant)
            ):
                continue
            interpreter = _interpreter_of(call)
            if interpreter:
                langs[str(call.args[0].value)] = interpreter
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


def _module_source(source: Source, module: str) -> tuple[str, bool]:
    """Read a module or package without requiring an installed esolangs."""
    from urllib.error import HTTPError

    relative = module.removeprefix("esolangs.").replace(".", "/")
    try:
        return source.get(relative + ".py"), False
    except FileNotFoundError:
        pass
    except HTTPError as exc:
        if exc.code != 404:
            raise
    return source.get(relative + "/__init__.py"), True


def _package_sources(source: Source, target: str) -> tuple[dict[str, str], set[str]]:
    """Collect runtime imports, retaining module namespaces and relative imports."""
    from importlib.util import resolve_name

    sources: dict[str, str] = {}
    packages: set[str] = set()

    def visit(module: str) -> None:
        if module in sources:
            return
        code, package = _module_source(source, module)
        sources[module] = code
        if package:
            packages.add(module)
        parent = module if package else module.rpartition(".")[0]
        tree = ast.parse(code)
        # Absolute imports inside helpers are lazy optional API dependencies;
        # relative imports inside steps are the interpreter's own code.
        imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
        imports.extend(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level and node not in imports
        )
        for node in imports:
            if node.level:
                dependency = resolve_name(
                    "." * node.level + (node.module or ""), parent
                )
            elif node.module and node.module.startswith("esolangs."):
                dependency = node.module
            else:
                continue
            if node.module is None and dependency not in packages:
                for alias in node.names:
                    visit(dependency + "." + alias.name)
                continue
            visit(dependency)
            if dependency in packages:
                # `from package import module` and exported values coexist.
                exported = ast.parse(sources[dependency])
                names = {
                    node.name
                    for node in exported.body
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                }
                names.update(
                    target.id
                    for node in exported.body
                    if isinstance(node, ast.Assign)
                    for target in node.targets
                    if isinstance(target, ast.Name)
                )
                names.update(
                    node.name.id
                    for node in exported.body
                    if isinstance(node, ast.TypeAlias)
                    and isinstance(node.name, ast.Name)
                )
                names.update(
                    alias.asname or alias.name
                    for node in exported.body
                    if isinstance(node, ast.ImportFrom) and node.module is not None
                    for alias in node.names
                )
                for alias in node.names:
                    if alias.name not in names:
                        visit(dependency + "." + alias.name)

    visit(target)
    visit(target + ".__main__")
    visit("esolangs.interpreters._entry")
    if "esolangs.raster" in sources:
        sources["esolangs.registry"] = _raster_registry(source, target)
        packages.add("esolangs.registry")
        visit("esolangs.registry._slug")
        visit("esolangs.settings")
        visit("esolangs._validate")
    return sources, packages


def _raster_registry(source: Source, target: str) -> str:
    """Return the selected raster language's metadata validation registry."""
    interpreter = target.removeprefix("esolangs.interpreters.")
    declarations = (
        node
        for text in _generator_modules(source)
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call) and _interpreter_of(node) == interpreter
    )
    declaration = next(declarations)
    name = ast.literal_eval(declaration.args[0])
    options = {keyword.arg: keyword.value for keyword in declaration.keywords}
    # These raster interpreters expose no dialect. Refuse a future dialect
    # rather than silently validating it as the default-only interpreter.
    if "dialect" in options and ast.literal_eval(options["dialect"]) is not None:
        raise ValueError("raster bundles with dialect settings are not supported")
    language_id = ast.literal_eval(options["id"]) if "id" in options else None
    registry = ast.parse(source.get("registry/__init__.py"))
    resolver = next(
        node
        for node in registry.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve"
    )
    return (
        "import difflib\nfrom types import SimpleNamespace\n"
        "from esolangs.exceptions import UnknownLanguageError\n"
        "from esolangs.registry._slug import canonical_id, SUGGESTION_CUTOFF\n"
        f"LANGUAGES = {{{name!r}: SimpleNamespace("
        "dialect=None, dialect_values=None)}\n"
        f"_BY_ID = {{({language_id!r} or canonical_id({name!r})): {name!r}}}\n"
        f"_BY_FOLDED = {{{name.strip().casefold()!r}: {name!r}}}\n"
        + ast.unparse(resolver)
        + "\n"
    )


_PACKAGE_RUNTIME = """
import builtins as _builtins
import importlib as _importlib
import importlib.abc as _import_abc
import importlib.util as _import_util
import sys as _sys

_prefix = "_esolangs_bundle_" + str(id(_sources))
_parents = {name.rpartition(".")[0] for name in _sources}
while any(name and name.rpartition(".")[0] not in _parents for name in tuple(_parents)):
    _parents.update(name.rpartition(".")[0] for name in tuple(_parents) if name)

class _BundleLoader(_import_abc.MetaPathFinder, _import_abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == _prefix or fullname.startswith(_prefix + "."):
            original = "esolangs" + fullname[len(_prefix):]
            if original not in _sources and original not in _parents:
                return None
            package = original in _packages or original not in _sources
            return _import_util.spec_from_loader(fullname, self, is_package=package)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        original = "esolangs" + module.__name__[len(_prefix):]
        code = _sources.get(original)
        if code is None:
            return
        module.__file__ = "<bundle>/" + original.replace(".", "/") + ".py"
        module.__dict__["__builtins__"] = dict(
            vars(_builtins), __import__=_bundle_import
        )
        exec(compile(code, module.__file__, "exec"), module.__dict__)


def _bundle_import(name, globals=None, locals=None, fromlist=(), level=0):
    if not level and (name == "esolangs" or name.startswith("esolangs.")):
        name = _prefix + name[len("esolangs"):]
    return _builtins.__import__(name, globals, locals, fromlist, level)

_sys.meta_path.insert(0, _BundleLoader())
_interpreter = _importlib.import_module(_prefix + _target[len("esolangs"):])
run = _interpreter.run

if __name__ == "__main__":
    _main = _sources[_target + ".__main__"]
    _globals = dict(vars(_interpreter), __name__="__main__")
    exec(compile(_main, "<bundle>/__main__.py", "exec"), _globals)
"""


def _bundle_package(source: Source, module: str, out: Path) -> Path:
    """Write a single file preserving package namespaces and optional dependencies."""
    target = "esolangs.interpreters." + module
    sources, packages = _package_sources(source, target)
    dependencies = []
    for name, pattern in (("Pillow", r"from PIL\b"), ("sympy", _SYMPY.pattern)):
        if any(re.search(pattern, code, re.M) for code in sources.values()):
            dependencies.append(f"# Requires: pip install {name}\n")
    code = (
        "#!/usr/bin/env python3\n"
        + "".join(dependencies)
        + f"_sources = {sources!r}\n_packages = {sorted(packages)!r}\n"
        + f"_target = {target!r}\n"
        + _PACKAGE_RUNTIME
    )
    compile(code, out.name, "exec")
    out.write_text(code)
    return out


def bundle(language: str, source: Source, out: Path | None) -> Path:
    """Write the self-contained interpreter bundle and return its path."""
    langs = _parse_registry(source)
    module = _resolve(language, langs)
    stem = module.rsplit(".", 1)[-1]
    if out is None:
        out = Path.cwd() / f"esolangs_{stem}.py"
    _code, package = _module_source(source, "esolangs.interpreters." + module)
    if package:
        return _bundle_package(source, module, out)
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
