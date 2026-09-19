"""Fail on a definition in ``src/`` that nothing in ``src/`` or ``scripts/`` reads.

A top-level def, class or constant is *dead* when no ``ast.Name`` or
``ast.Attribute`` outside its own definition, and outside import
statements, names it.  Two routes (Minifuck's staged and sculpted) and the
Eval reorder catalog sat that way, each with a test suite of
its own, because a replaced construction keeps its tests green.

The rule is deliberately narrow:

- every top-level name in ``src/esolangs/tools/`` (the generators, where
  the dead routes accumulated), and
- every leading-underscore name anywhere else in ``src/``.

A public name outside ``tools/`` is package API and may be consumed by the
suite alone (``vm.py``'s termination provers), so it is not judged here.
Dunder names are protocol hooks.  ``from m import x as y`` counts a use of
``y`` as a use of ``x``.  Tests are not read: a name only a test reaches is
exactly the case to report, and the fix is to move it under ``tests/``.

Run::

    python scripts/check_dead_definitions.py           # the repo
    python scripts/check_dead_definitions.py ROOT      # another tree
"""

import ast
import pathlib
import sys
from collections import Counter

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _top_level_names(node: ast.stmt) -> set[str]:
    """Return the names ``node`` binds at module level, or the empty set."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return {node.name}
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    if isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
        return {node.name.id}
    return set()


def _aliases(tree: ast.Module) -> dict[str, str]:
    """Map every ``from m import x as y`` alias to the name it aliases."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
    return aliases


def _tally(counts: Counter[str], sub: ast.AST, aliases: dict[str, str]) -> None:
    """Add one node's contribution, de-aliased, to *counts*."""
    if isinstance(sub, ast.Name):
        counts[aliases.get(sub.id, sub.id)] += 1
    elif isinstance(sub, ast.Attribute):
        counts[sub.attr] += 1
    elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
        # A forward reference: ``"_State | _Halt | None"``.  Docstrings do not
        # parse as an expression and drop out here.
        for name in _forward_names(sub.value):
            counts[aliases.get(name, name)] += 1


def _references(tree: ast.Module) -> Counter[str]:
    """Count every name read in ``tree`` outside import statements, de-aliased."""
    aliases = _aliases(tree)
    counts: Counter[str] = Counter()
    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        for sub in ast.walk(node):
            _tally(counts, sub, aliases)
    return counts


def _forward_names(text: str) -> set[str]:
    """Return the names in a string that parses as one expression, else none."""
    if "\n" in text or len(text) > 200:
        return set()
    try:
        expr = ast.parse(text, mode="eval")
    except SyntaxError:
        return set()
    return {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)}


def _judged(path: pathlib.Path, root: pathlib.Path, name: str) -> bool:
    """Whether ``name`` defined in ``path`` is one this check reports."""
    if name.startswith("__") and name.endswith("__"):
        return False
    if root / "src" / "esolangs" / "tools" in path.parents:
        return True
    return name.startswith("_")


def dead_definitions(root: pathlib.Path) -> list[tuple[pathlib.Path, str, int]]:
    """Return ``(path, name, lines)`` for every judged name nothing reads."""
    trees = {
        p: ast.parse(p.read_text(), filename=str(p))
        for d in ("src", "scripts")
        for p in sorted((root / d).rglob("*.py"))
    }
    total: Counter[str] = Counter()
    for tree in trees.values():
        total += _references(tree)
    found = []
    for path, tree in trees.items():
        if root / "src" not in path.parents:
            continue
        for node in tree.body:
            names = _top_level_names(node)
            if not names or not all(_judged(path, root, n) for n in names):
                continue
            own = _references(ast.Module(body=[node], type_ignores=[]))
            if all(total[n] - own[n] == 0 for n in names):
                size = (node.end_lineno or node.lineno) - node.lineno + 1
                found.append((path, sorted(names)[0], size))
    return found


def main() -> None:
    """Report every dead definition; exit 1 if any."""
    root = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else _ROOT
    found = dead_definitions(root)
    for path, name, size in found:
        where = path.relative_to(root)
        print(f"{where}: {name} ({size} lines) has no reader in src/ or scripts/")
    if found:
        print(f"\n{len(found)} dead: delete, or move a test-only oracle under tests/")
        raise SystemExit(1)
    print("no dead definitions")


if __name__ == "__main__":
    main()
