"""``new_language.py remove``: delete a language and every entry naming it.

Split from ``new_language.py``, which re-exports what its callers use.  The
inverse of ``start``/``check``/``finish``: it deletes what ``check`` asks
for, cuts the language's entries out of the shared tables it knows, keeps a
module the remaining source still imports (minus its ``LANGUAGE``),
regenerates, and lists the mentions left in prose.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).parents[1]
#: Where a language's own test and script files live.
_TREES = ("tests", "scripts")


def _tests_attr(module: str, attr: str) -> Any:
    """Read ``attr`` from ``tests.<module>``, which needs the repo on the path."""
    sys.path.insert(0, str(ROOT))
    try:
        return getattr(importlib.import_module(f"tests.{module}"), attr)
    finally:
        sys.path.remove(str(ROOT))


def _gone(module: str | None, modules: set[str]) -> bool:
    """Whether ``module`` is one of ``modules`` or inside one of them."""
    return module is not None and any(
        module == m or module.startswith(m + ".") for m in modules
    )


def _whole_statement(
    node: ast.AST, named: Callable[[ast.AST | None], bool], modules: set[str]
) -> bool:
    """Whether ``node`` is a statement that exists only for the language.

    ``X["Name"] = ...``, ``run_x = _runner("module")``, and an import from
    the language's own interpreter or generator module.
    """
    if isinstance(node, ast.ImportFrom):
        return _gone(node.module, modules)
    if isinstance(node, ast.If) and not node.orelse:
        # ``if name == "123": ...``: a branch taken for the language alone.
        test = node.test
        terms = (
            test.values
            if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And)
            else [test]
        )
        return any(
            isinstance(term, ast.Compare)
            and [type(op) for op in term.ops] == [ast.Eq]
            and (named(term.left) or named(term.comparators[0]))
            for term in terms
        )
    if isinstance(node, ast.FunctionDef | ast.ClassDef):
        # A helper importing the language's modules lazily serves it alone.
        return any(
            isinstance(inner, ast.ImportFrom) and _gone(inner.module, modules)
            for inner in ast.walk(node)
        )
    if not isinstance(node, ast.Assign):
        return False
    if any(isinstance(t, ast.Subscript) and named(t.slice) for t in node.targets):
        return True
    # ``run_one_two_three = _runner("one_two_three")``: named after its key.
    call = node.value
    return (
        isinstance(call, ast.Call)
        and [*map(named, call.args)] == [True]
        and len(node.targets) == 1
        and isinstance(target := node.targets[0], ast.Name)
        and re.sub(r"\W+", "_", str(call.args[0].value).rsplit(".")[-1].lower())  # type: ignore[attr-defined]
        in target.id.lower()
    )


def _drop_entries(
    path: Path,
    keys: set[str],
    modules: set[str],
    external: set[str] | frozenset[str] = frozenset(),
) -> int:
    """Delete every dict entry, list item or ``X[key] = ...`` keyed by ``keys``.

    Located by AST and cut by line, so an entry must own its lines; one
    sharing a line with another is left for the leftover report.  A helper
    ``external`` still names (``sbleq_variant``, shared by the S*bleq
    variants) is kept even when it reads a name the removal deletes.
    """
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []

    def named(node: ast.AST | None) -> bool:
        return isinstance(node, ast.Constant) and node.value in keys

    def own(first: ast.expr, last: ast.expr) -> None:
        """Take an entry's lines only if nothing else shares them."""
        before = lines[first.lineno - 1][: first.col_offset]
        after = lines[last.end_lineno - 1][last.end_col_offset :]  # type: ignore[operator]
        if not before.strip() and after.strip() in {"", ","}:
            lo, hi = first.lineno, last.end_lineno or last.lineno
            # Its comment goes too, unless a sibling below still sits under it.
            following = lines[hi].strip() if hi < len(lines) else ""
            if not following or following[0] in "#)]}":
                while lo > 1 and lines[lo - 2].strip().startswith("#"):
                    lo -= 1
            spans.append((lo, hi))

    # A statement alone in its block cannot go without leaving it empty.
    parsed = ast.parse(source)
    lonely = {
        id(block[0])
        for parent in ast.walk(parsed)
        for field in ("body", "orelse", "finalbody")
        if isinstance(block := getattr(parent, field, None), list) and len(block) == 1
    }
    for node in ast.walk(parsed):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if key is not None and named(key):
                    own(key, value)
        elif isinstance(node, ast.List | ast.Set | ast.Tuple):
            for item in node.elts:
                # A bare key, or a ``Language("Name", ...)`` naming it.
                first = (
                    item.args[0] if isinstance(item, ast.Call) and item.args else None
                )
                if named(item) or named(first):
                    own(item, item)
        elif (
            isinstance(node, ast.stmt)
            and not (isinstance(node, ast.If) and id(node) in lonely)
            # A function another file still names stays, even if it lazily
            # imports the module going (``sbleq_variant``).
            and not (
                isinstance(node, ast.FunctionDef | ast.ClassDef)
                and node.name in external
            )
            and _whole_statement(node, named, modules)
        ):
            decorators = getattr(node, "decorator_list", [])
            top = lo = min([node.lineno, *(d.lineno for d in decorators)])
            # A comment block right above is its own when the two stand as
            # a paragraph, blank lines on both sides; otherwise it may head
            # a run of siblings (``# BEGIN GENERATED EXPORTS``).
            end = node.end_lineno or node.lineno
            while lo > 1 and lines[lo - 2].strip().startswith("#"):
                lo -= 1
            if lo < top and (
                (lo > 1 and lines[lo - 2].strip())
                or (end < len(lines) and lines[end].strip())
            ):
                lo = top
            spans.append((lo, node.end_lineno or node.lineno))
    # A top-level function or class using a name imported from a deleted
    # module goes too, and so, in turn, does whatever uses it.
    tree = ast.parse(source)
    dead = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and _gone(node.module, modules)
        for alias in node.names
    } | {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.ClassDef)
        and any(lo <= node.lineno <= hi for lo, hi in spans)
    }
    while True:
        spanned = {lo for lo, _ in spans}
        more = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.ClassDef)
            and node.name not in dead
            and node.name not in external
            and any(
                isinstance(inner, ast.Name)
                and inner.id in dead
                # A use inside a cut branch goes with the branch.
                and not any(lo <= inner.lineno <= hi for lo, hi in spans)
                for inner in ast.walk(node)
            )
        ]
        if not more:
            break
        for node in more:
            dead.add(node.name)
            top = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            if top not in spanned:
                spans.append((top, node.end_lineno or node.lineno))
    # A span inside another (a nested helper, an entry of a dropped table)
    # goes with the outer one; cutting both would cut the outer twice.
    spans = [
        span
        for span in set(spans)
        if not any(o != span and o[0] <= span[0] and span[1] <= o[1] for o in spans)
    ]
    # An import another language still uses stays (Cyclic tag reuses BCT's
    # PAIR); judged on the source with every other cut already made.
    imports = {
        node.end_lineno or node.lineno: node
        for node in ast.parse(source).body
        if isinstance(node, ast.ImportFrom)
    }
    kept = [*lines]
    for lo, hi in sorted(set(spans), reverse=True):
        del kept[lo - 1 : hi]
    used = {
        node.id
        for node in ast.walk(ast.parse("".join(kept)))
        if isinstance(node, ast.Name)
    }
    spans = [
        span
        for span in spans
        if span[1] not in imports
        or not {a.asname or a.name for a in imports[span[1]].names} & used
    ]
    for lo, hi in sorted(set(spans), reverse=True):
        del lines[lo - 1 : hi]
    if spans:
        path.write_text("".join(lines), encoding="utf-8")
    return len(spans)


def _drop_inline_items(path: Path, keys: set[str]) -> int:
    """Cut each item keyed by ``keys`` that shares its line with others.

    ``frozenset({"A Painter Ant", "Suffolk"})`` holds two languages on one
    line, which :func:`_drop_entries` leaves.  Cut by column instead, with
    the separating comma; a container left empty is spelled empty.
    """
    cuts = 0
    while True:
        source = path.read_bytes()
        starts = [0]
        for line in source.splitlines(keepends=True):
            starts.append(starts[-1] + len(line))

        def at(line: int, col: int, starts: list[int] = starts) -> int:
            return starts[line - 1] + col

        def span(node: ast.AST) -> tuple[int, int]:
            return (
                at(node.lineno, node.col_offset),  # type: ignore[attr-defined]
                at(node.end_lineno, node.end_col_offset),  # type: ignore[attr-defined]
            )

        cut: tuple[int, int, bytes] | None = None
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Dict) and None not in node.keys:
                items = [
                    (span(k)[0], span(v)[1], isinstance(k, ast.Constant) and k.value)
                    for k, v in zip(node.keys, node.values, strict=True)
                    if k is not None
                ]
                empty = b"{}"
            elif isinstance(node, ast.List | ast.Set | ast.Tuple):
                items = [
                    (*span(e), isinstance(e, ast.Constant) and e.value)
                    for e in node.elts
                ]
                empty = {ast.List: b"[]", ast.Set: b"set()", ast.Tuple: b"()"}[
                    type(node)
                ]
            else:
                continue
            for i, (lo, hi, value) in enumerate(items):
                if not isinstance(value, str) or value not in keys:
                    continue
                if len(items) == 1:
                    cut = (*span(node), empty)
                elif i + 1 < len(items):
                    cut = (lo, items[i + 1][0], b"")
                else:
                    cut = (items[i - 1][1], hi, b"")
                break
            if cut:
                break
        if cut is None:
            return cuts
        lo, hi, text = cut
        path.write_bytes(source[:lo] + text + source[hi:])
        cuts += 1


def _drop_json(path: Path, prune: Callable[[object], object]) -> None:
    """Rewrite ``path`` through ``prune``, keeping its indent and escaping."""
    text = path.read_text(encoding="utf-8")
    indent = len(text.split("\n", 2)[1]) - len(text.split("\n", 2)[1].lstrip())
    pruned = prune(json.loads(text))
    out = json.dumps(pruned, indent=indent, ensure_ascii=text.isascii())
    path.write_text(out + "\n" * text.endswith("\n"), encoding="utf-8")


def _drop_toml(path: Path, name: str) -> None:
    """Drop ``name``'s ``[[...]]`` block and ``"name" = ...`` lines from ``path``.

    Text, not a parse and rewrite, so the file's comments and folding stay.
    """
    text = path.read_text(encoding="utf-8")
    quoted = json.dumps(name, ensure_ascii=False)
    # Each block runs from its header to the next; the head has none.
    blocks = re.split(r"\n(?=\[)", text)
    kept = []
    for block in blocks:
        if (
            block.startswith("[[")
            and tomllib.loads(block.split("\n", 1)[1]).get("generator") == name
        ):
            continue
        lines = block.split("\n")
        kept.append(
            "\n".join(
                line
                for line in lines
                if not re.match(
                    rf"({re.escape(quoted)}|{re.escape(name)}) =",
                    line,
                )
            )
        )
    path.write_text("\n".join(kept), encoding="utf-8")


def _drop_bullets(path: Path, name: str) -> None:
    """Drop each ``- name ...`` or ``- [name](...) ...`` bullet from ``path``.

    Its indented lines go with it, ``- **name:**`` counts too, and a blank
    line that only separated the bullet from the next goes as well.
    """
    text = path.read_text(encoding="utf-8")
    bullet = rf"(?m)^- \[?(?:\*\*)?{re.escape(name)}(?:\*\*)?\]?(?!\w).*\n(?:  .*\n)*"

    def cut(match: re.Match[str]) -> str:
        before = text[: match.start()]
        if before.endswith("\n\n") and text.startswith("\n", match.end()):
            return "\0"  # marks the separator below for removal
        return ""

    text = re.sub(bullet, cut, text).replace("\0\n", "")
    path.write_text(text, encoding="utf-8")


def _owned_test_files(lang: Language) -> list[Path]:
    """Return the test files the coupling guard counts as ``lang``'s own.

    One rule for both: a file the guard lets name the language goes with it.
    A prefix that does not end a path segment must be followed by ``.``,
    ``/`` or ``_``, so stem ``line`` does not take ``lines.toml``.  A file
    another language claims by a longer prefix is that one's: Piet does not
    take ``test_boolean_piet_plus_plus.py``.
    """
    from esolangs.registry import LANGUAGES

    own = _tests_attr("test_language_coupling", "_own")
    files = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", *_TREES],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    def claim(prefixes: tuple[str, ...], path: str) -> int:
        """Return the length of the longest prefix claiming ``path``, or 0."""
        return max(
            (
                len(prefix)
                for prefix in prefixes
                if prefix.startswith(("tests/", "scripts/"))
                and path.startswith(prefix)
                and (prefix.endswith(("/", "_", ".py")) or path[len(prefix)] in "./_")
            ),
            default=0,
        )

    mine = own(lang)[1]
    others = [own(other)[1] for other in LANGUAGES.values() if other is not lang]
    return [
        ROOT / path
        for path in files
        if (length := claim(mine, path))
        and all(claim(prefixes, path) <= length for prefixes in others)
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
    """Return the ``esolangs.tools`` module whose ``LANGUAGE`` is ``lang``."""
    for module_name, module in sorted(sys.modules.items()):
        if (
            module_name.startswith("esolangs.tools.")
            and getattr(module, "LANGUAGE", None) is lang
        ):
            return module_name
    return None


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
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module]
                names += [f"{node.module}.{alias.name}" for alias in node.names]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for module in names:
                if module.startswith(("esolangs.", "tests.")):
                    users.setdefault(module, set()).add(path)
    return users


def _within(path: str, doomed: set[Path]) -> bool:
    """Whether repo-relative ``path`` is one of, or inside one of, ``doomed``."""
    full = ROOT / path
    return any(full == d or d in full.parents for d in doomed)


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
    ``tests/tools/test_circuit_free_columns.py`` (importing
    ``esolangs.tools.circuit_diagram.free_columns``) is caught here instead;
    it cannot run once the module is gone.
    """
    candidates = {
        user
        for imported, importers in users.items()
        for gone in gone_modules
        if imported == gone or imported.startswith(gone + ".")
        for user in importers
        if user.startswith("tests/") and not _within(user, doomed)
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
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                imports.add(node.module)
                imports.update(f"{node.module}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
        found = {
            m
            for m in imports
            if m in {"esolangs", "tests"} or m.startswith(("esolangs.", "tests."))
        }
        if found and all(_gone(m, gone_modules) for m in found):
            dead.add(full)
    return dead


def _stale_timing(key: str, names: set[str], gone_paths: set[str]) -> bool:
    """Whether a recorded pytest node ID names a deleted test or language.

    A shared test carries the language as one of its parametrize ids
    (``...[Suffolk-one_hot]``, ``...[1-Line]``); a language's own test carries
    its file path.  ``Piet`` must not take ``Piet++``'s rows: only a whole
    ``-``-delimited component counts.
    """
    if key.split("::", 1)[0] in gone_paths:
        return True
    match = re.search(r"\[([^\]]*)\]", key)
    if match is None:
        return False
    param = match.group(1)
    return any(
        param == n
        or param.startswith(n + "-")
        or param.endswith("-" + n)
        or f"-{n}-" in param
        for n in names
    )


def _top_level_name(node: ast.stmt) -> str | None:
    """Return the name a top-level statement binds, if it binds one."""
    if isinstance(node, ast.FunctionDef | ast.ClassDef):
        return node.name
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _names_used(tree: ast.AST) -> set[str]:
    """Return the names a module reads, and the attributes it reaches.

    Store targets count too: ``X |= ...`` reads ``X``, and keeping a name that
    appears anywhere is safe where cutting a live definition is not.
    """
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    return used


def _drop_name_items(path: Path, names: set[str]) -> int:
    """Cut each ``ast.Name`` element named in ``names`` from a container.

    ``_MULTILINE_WRAPPERS = frozenset({_taglate, ...})`` and the
    ``_token_patterns`` dict name wrappers directly, so the membership must go
    before the definition reads as dead.
    """
    cuts = 0
    while True:
        source = path.read_bytes()
        starts = [0]
        for line in source.splitlines(keepends=True):
            starts.append(starts[-1] + len(line))

        def at(line: int, col: int, starts: list[int] = starts) -> int:
            return starts[line - 1] + col

        def span(node: ast.AST) -> tuple[int, int]:
            return (
                at(node.lineno, node.col_offset),  # type: ignore[attr-defined]
                at(node.end_lineno, node.end_col_offset),  # type: ignore[attr-defined]
            )

        cut: tuple[int, int, bytes] | None = None
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Dict):
                if None in node.keys:
                    continue
                items = [
                    (
                        span(key)[0],
                        span(value)[1],
                        key.id if isinstance(key, ast.Name) else None,
                    )
                    for key, value in zip(node.keys, node.values, strict=True)
                    if key is not None
                ]
                empty = b"{}"
            elif isinstance(node, ast.List | ast.Set):
                items = [
                    (
                        *span(element),
                        element.id if isinstance(element, ast.Name) else None,
                    )
                    for element in node.elts
                ]
                empty = {ast.List: b"[]", ast.Set: b"set()"}[type(node)]
            else:
                continue
            for index, (lo, hi, value) in enumerate(items):
                if value not in names:
                    continue
                if len(items) == 1:
                    cut = (*span(node), empty)
                elif index + 1 < len(items):
                    cut = (lo, items[index + 1][0], b"")
                else:
                    cut = (items[index - 1][1], hi, b"")
                break
            if cut:
                break
        if cut is None:
            return cuts
        lo, hi, text = cut
        path.write_bytes(source[:lo] + text + source[hi:])
        cuts += 1


def _drop_dead_code(path: Path, external: set[str]) -> int:
    """Cut top-level definitions and constants no surviving code names.

    After the language's ``SPECS[...]`` entry and ``LANGUAGE`` are gone, its
    generator functions and wrapper are dead.  ``external`` is every name the
    rest of the tree reads; a helper another entry or language still names
    stays reachable, and so does anything an uncut top-level statement reads.
    """
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)
    nodes = {
        name: node
        for node in tree.body
        if (name := _top_level_name(node)) is not None and not name.startswith("__")
    }
    roots = set(external)
    for node in tree.body:
        if _top_level_name(node) is None:
            roots |= _names_used(node)
    live: set[str] = set()
    pending = [name for name in nodes if name in roots]
    while pending:
        name = pending.pop()
        if name in live:
            continue
        live.add(name)
        pending += [
            ref for ref in _names_used(nodes[name]) if ref in nodes and ref not in live
        ]
    dead = [nodes[n] for n in nodes if n not in live]
    if not dead:
        return 0
    spans: list[tuple[int, int]] = []
    for node in dead:
        lo, hi = node.lineno, node.end_lineno or node.lineno
        # A ``# --- Name ---`` section head goes with its definition.
        while lo > 1 and lines[lo - 2].strip().startswith("#"):
            lo -= 1
        spans.append((lo, hi))
    spans = [
        span
        for span in set(spans)
        if not any(o != span and o[0] <= span[0] and span[1] <= o[1] for o in spans)
    ]
    for lo, hi in sorted(spans, reverse=True):
        del lines[lo - 1 : hi]
    path.write_text("".join(lines), encoding="utf-8")
    return len(spans)


def _drop_from_series(path: Path, name: str, tail: str) -> None:
    """Drop ``name`` from the prose list ``A, B, C and D <tail>`` in ``path``.

    Whitespace, line breaks included, is kept where it fell, so the wrapped
    paragraph stays wrapped; the last two items keep their ``and``.
    """
    text = path.read_text(encoding="utf-8")
    flat = " ".join(text.split())
    match = re.search(rf"([\w,\-~/ ()]+?) {tail}", flat)
    if not match:
        return
    items = [p.strip() for p in re.split(r",| and ", match.group(1)) if p.strip()]
    if name not in items:
        return
    sep = r"\s+"
    region = re.search(re.escape(match.group(1)).replace(r"\ ", sep) + sep + tail, text)
    assert region, tail
    part = region.group()
    word = re.escape(name).replace(r"\ ", sep)
    if items[-1] == name:
        # "Y, X and Name tail" becomes "Y and X tail".
        pattern = rf",(\s+)([^,]+?)\s+and\s+{word}(\s+{tail.split()[0]})"
        part, n = re.subn(pattern, r" and\1\2\3", part, count=1)
        if not n:  # only two items: "X and Name tail"
            part = re.sub(rf"\s+and\s+{word}(?=\s+{tail.split()[0]})", "", part)
    elif items[-2] == name:
        part = re.sub(rf",?(\s+){word}\s+and(\s+)", r"\1and\2", part, count=1)
        part = part.replace(" and\nand", " and")  # never two ``and``s
    else:
        part = re.sub(
            rf"([ \t]?)(?<![\w~/]){word},[ \t]*(\n?)",
            lambda m: m.group(2) or m.group(1),
            part,
            count=1,
        )
    text = text[: region.start()] + part + text[region.end() :]
    path.write_text(text, encoding="utf-8")


#: The files ``remove`` cuts the language's entries out of by itself; the
#: coupling guard does not count them for the same reason.
_EDITED = (
    "src/esolangs/registry/_table.py",
    "src/esolangs/tools/__init__.py",
    "tests/samples.py",
    "tests/tools/boolean_runners.py",
    "tests/tools/test_wrap.py",
    "tests/proofs/test_execution_formulas.py",
    "tests/proofs/test_workspace_formulas.py",
    "tests/proofs/test_schemes.py",
    "tests/test_interpreter_only_admissions.py",
    "tests/proofs/test_bands.py",
)


def _mention_edit(mention: str) -> str:
    """Label a leftover mention by the edit it needs.

    ``git grep -n`` prints ``path:line:text`` and the path decides the kind.
    The tool never rewrites these itself: a runnable example needs a
    replacement language (Alight's ``expression_syntax`` has no successor),
    and a comment or prose line needs a sentence a human stands behind.
    """
    path = mention.split(":", 1)[0]
    if path == "src/esolangs/cli_help.py":
        return "example: choose a replacement language"
    if path.startswith("docs/") or path.endswith(".md"):
        return "prose: reword or drop the mention"
    return "comment: reword or drop the mention"


def remove(name: str) -> list[str]:
    """Delete ``name`` everywhere ``check`` looks; return the leftover mentions."""
    from esolangs.registry import LANGUAGES, example_stems

    reference = _tests_attr("test_language_coupling", "REFERENCE")
    if name == reference:
        raise ValueError(
            f"{reference} is the reference language: shared tests, the example "
            "commands and scripts/docs/generate.py spell it out, so it is not "
            "removable"
        )
    lang = LANGUAGES[name]
    module = lang.interpreter or ""
    gen = lang.boolean.__name__ if lang.boolean else lang.id
    declaring = _declaring_module(lang)
    stem = example_stems().get(lang.id, "")
    own_modules = {f"esolangs.interpreters.{module}"} if module else set()
    if declaring:
        own_modules.add(declaring)
    module_paths = {p for m in own_modules if (p := _module_path(m))}
    files = _python_files()
    users = _imported([f for f in files if f not in _EDITED])
    ids = {other.id for other in LANGUAGES.values()}
    # Every wiki fixture whose name begins with this id and no longer one:
    # ``slashes_*.txt`` go with ``///``, not ``piet_plus_plus.toml`` with Piet.
    wiki = [
        path
        for path in (ROOT / "tests/fixtures/wiki_examples").iterdir()
        if path.is_file() and _owner_id(path.name, ids) == lang.id
    ]
    doomed: set[Path] = {
        *module_paths,
        ROOT / f"tests/interpreters/test_{lang.id}.py",
        ROOT / f"tests/tools/test_boolean_{gen}.py",
        *wiki,
        *(ROOT / "src/esolangs/examples").glob(f"{stem}.*" if stem else "-"),
        *_owned_test_files(lang),
    }
    doomed |= _dead_test_files(doomed, _gone_modules(doomed), users)
    doomed |= _orphans(doomed, users)
    # A ``src`` module the remaining code imports stays, minus its
    # ``LANGUAGE``: the shared helper outlives the language that defined it.
    kept: list[str] = []
    while True:
        needed = {
            path
            for path in doomed
            if path.is_relative_to(ROOT / "src")
            and path.suffix != ".txt"
            and any(
                user.startswith("src/") and not _within(user, doomed)
                for imported, importers in users.items()
                if imported == _module_of(path)
                or imported.startswith(_module_of(path) + ".")
                for user in importers
            )
        }
        if not needed:
            break
        doomed -= needed
        for path in sorted(needed):
            importers = sorted(
                {
                    user
                    for imported, found in users.items()
                    if imported == _module_of(path)
                    or imported.startswith(_module_of(path) + ".")
                    for user in found
                    if user.startswith("src/") and not _within(user, doomed | {path})
                }
            )
            shown = path.relative_to(ROOT)
            kept.append(f"{shown}: kept, still imported by {', '.join(importers)}")
    # ``git rm``, not unlink: tests read ``git ls-files``, which would still
    # list a file deleted only from disk.
    subprocess.run(
        ["git", "rm", "-q", "-r", "--ignore-unmatch", *map(str, sorted(doomed))],
        cwd=ROOT,
        check=True,
    )
    # ``git rm`` skips a file never committed: a language removed before its
    # first commit would otherwise stay registered.
    for doomed_path in doomed:
        if doomed_path.is_file():
            doomed_path.unlink()
        elif doomed_path.is_dir():
            for leftover in sorted(doomed_path.rglob("*"), reverse=True):
                if leftover.is_file() or leftover.is_symlink():
                    leftover.unlink()
                else:
                    leftover.rmdir()
            doomed_path.rmdir()
    for path in module_paths - doomed:
        if declaring and path == _module_path(declaring):
            _drop_language_statement(path / "__init__.py" if path.is_dir() else path)
    keys = {name, module, lang.id, gen, stem} - {""}
    # ``Path("tests/interpreters/test_inject.py")`` in a support list.
    paths = {str(p.relative_to(ROOT)) for p in doomed}
    # A deleted test module too: ``tests/samples.py`` borrows Inject's program.
    gone_modules = _gone_modules(doomed)
    modules = {m for m in own_modules if _module_path(m) is None} | gone_modules
    edited = [*_EDITED]
    # Names each surviving file reads.  A helper another file still names is
    # kept even when it reads a name this removal deletes: ``sbleq_variant``
    # serves every S*bleq variant, not just the one going.
    surviving = [f for f in files if not _within(f, doomed) and (ROOT / f).is_file()]
    used_by_file = {
        f: _names_used(ast.parse((ROOT / f).read_text(encoding="utf-8")))
        for f in surviving
    }

    def external_for(relative: str) -> set[str]:
        names: set[str] = set()
        for other, used in used_by_file.items():
            if other != relative:
                names |= used
        return names

    for relative in edited:
        _drop_entries(ROOT / relative, keys | paths, modules, external_for(relative))
        _drop_inline_items(ROOT / relative, keys)

    def prune(node: object) -> object:
        if isinstance(node, dict):
            return {k: prune(v) for k, v in node.items() if k != name}
        if isinstance(node, list):
            return [
                prune(item)
                for item in node
                if not (isinstance(item, dict) and item.get("generator") == name)
            ]
        return node

    _drop_json(ROOT / "tests/fixtures/generator_sizes.json", prune)
    # Timing snapshots keep one entry per pytest node ID; drop the removed
    # language's parametrized rows and its own deleted test files.
    timings = ROOT / "tests/fixtures/slow_durations.json"

    def drop_timings(node: object) -> object:
        if not isinstance(node, dict):
            return node
        names = {name, lang.id, *lang.aliases}
        return {
            key: value
            for key, value in node.items()
            if not _stale_timing(str(key), names, paths)
        }

    if timings.is_file():
        _drop_json(timings, drop_timings)
    for relative in (
        "tests/fixtures/curation.toml",
        "src/esolangs/proof_status.toml",
        "tests/fixtures/sharing_catalogue.toml",
        "tests/fixtures/canonical_folding_catalogue.toml",
    ):
        _drop_toml(ROOT / relative, name)
    for relative in ("docs/limitations.md", "docs/proofs/index.md"):
        _drop_bullets(ROOT / relative, name)
    _drop_from_series(ROOT / "docs/proofs/index.md", name, "keeps? no tree route")
    tuning = ROOT / "tests/fixtures/deep_arities.toml"
    tuning.write_text(
        "".join(
            line
            for line in tuning.read_text(encoding="utf-8").splitlines(keepends=True)
            if line.split(" = ", 1)[0] not in keys
        ),
        encoding="utf-8",
    )
    # A cut entry can leave its import unused; the linter knows which.
    shared = ["src/esolangs/tools/wrap.py"]
    touched = [
        *[str(p.relative_to(ROOT)) for p in module_paths - doomed],
        *edited,
        *shared,
    ]
    ruff = Path(sys.executable).parent / "ruff"
    subprocess.run(
        [str(ruff), "check", "--fix", "--select", "F401,I", "-q", *touched],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    # Dead code the language left in the shared modules: its wrapper in
    # ``wrap.py``.  The unused imports are gone, so a top-level name nothing
    # reads is dead.
    wrapper = getattr(lang.wrap, "__name__", None) if lang.wrap else None
    exclusive = False
    if wrapper is not None and not any(
        other is not lang and other.wrap is lang.wrap for other in LANGUAGES.values()
    ):
        exclusive = True
        _drop_name_items(ROOT / "src/esolangs/tools/wrap.py", {wrapper})
    for relative in shared:
        _drop_dead_code(ROOT / relative, external_for(relative))
    subprocess.run(
        [str(ruff), "format", "-q", *touched],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    for target in ("docs", "examples"):
        subprocess.run(
            [sys.executable, "scripts/docs/generate.py", target],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    # Other files now name fewer languages; the coupling ceiling follows.  A
    # fresh process: this one's registry still holds the removed language.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from tests.test_language_coupling import lower_recorded; lower_recorded()",
        ],
        cwd=ROOT,
        check=True,
    )
    # An import of a deleted module fails wherever it runs.
    broken = sorted(
        f"{user}: imports {imported}, which is gone"
        for imported, importers in users.items()
        for gone in gone_modules
        if imported == gone or imported.startswith(gone + ".")
        for user in importers
        if not _within(user, doomed)
    )
    survived = sorted(
        f"{path}: still present after its language went"
        for path in paths
        if (ROOT / path).exists()
    )
    # Prose and comments name a language by its display name and aliases; the
    # id and module are ordinary words (``line``, ``back``) far too often to
    # grep bare, so they count only inside quotes or a dotted module path.
    shadowed = any(other != name and other.startswith(name) for other in LANGUAGES)
    tokens = {name, *lang.aliases}
    if name.isdigit() or shadowed:
        tokens.discard(name)
    if exclusive and wrapper is not None:
        # The wrapper's own name is not the language's; surface the tests that
        # still name it (``WRAPPERS[...] is _bio``) so the hand edit is found.
        tokens.add(wrapper)
    patterns = list(tokens)
    patterns += [
        f"{quote}{token}{quote}"
        for token in {name, lang.id, *lang.aliases}
        for quote in ('"', "'", "`")
    ]
    if module:
        patterns.append(f"esolangs.interpreters.{module}")
    if declaring:
        patterns.append(declaring)
    patterns = list(dict.fromkeys(patterns))
    args: list[str] = []
    for pattern in patterns:
        args += ["-e", pattern]
    grep = subprocess.run(
        ["git", "grep", "-n", "-I", "-F", "-w", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # The tool's own examples name languages (``Piet++``, ``[1-Line]``), and
    # the changelog records that they existed; neither is coupling to edit,
    # so leave both out of the report.  Label what each remaining mention
    # needs: the tool cannot rewrite prose or a runnable example without
    # inventing a claim, so the edit stays with the caller.
    mentions = [
        f"[{_mention_edit(line)}] {line}"
        for line in grep.stdout.splitlines()
        if not line.startswith(("scripts/remove_language.py:", "CHANGELOG.md:"))
    ]
    return kept + survived + broken + mentions
