"""Classify each boolean generator by the machinery it actually reaches.

What keeps the totality table in ``docs/proofs.md`` honest: it is the set
of rows that goes stale silently, since a generator gaining a loop or a
refusal looks exactly like one that always had neither.  Re-run this when
that table is in question and diff the two columns against it.

Module-level grep is too coarse: one module holds a dozen generators and
they do not share callees.  This walks the call graph from each
generator's own function and reports every unbounded loop and every raise
inside the reachable set.

Resolution is *import-aware*, which is the whole difficulty.  A name-only
graph links any call to every definition sharing its name, and the private
helpers here collide across modules -- it put Minifuck inside 123's
constructor, which Minifuck does not import.  A name is resolved here to a
definition in the caller's own module, or to the module the caller's
``from ... import`` names, and to nothing otherwise.
"""

import ast
import importlib
import inspect
import pkgutil
from collections import defaultdict

import esolangs.tools.boolean as boolean
from esolangs.registry import BY_BOOLEAN

PACKAGE = "esolangs.tools.boolean"
Key = tuple[str, str]

#: (module, function) -> its ast node.
NODES: dict[Key, ast.FunctionDef] = {}
#: module -> name -> module the name was imported from.
IMPORTS: dict[str, dict[str, str]] = defaultdict(dict)

for info in pkgutil.iter_modules(boolean.__path__):
    if info.name == "examples":
        continue
    tree = ast.parse(inspect.getsource(importlib.import_module(
        f"{PACKAGE}.{info.name}"
    )))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            NODES.setdefault((info.name, node.name), node)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith(PACKAGE):
                origin = node.module.rsplit(".", 1)[-1]
                for alias in node.names:
                    IMPORTS[info.name][alias.asname or alias.name] = origin


def calls(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Name):
                out.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                out.add(fn.attr)
    return out


def resolve(module: str, name: str) -> Key | None:
    """Where a call to ``name`` inside ``module`` lands, if anywhere here."""
    if (module, name) in NODES:
        return module, name
    origin = IMPORTS[module].get(name)
    if origin is not None and (origin, name) in NODES:
        return origin, name
    return None


def reach(start: Key) -> set[Key]:
    seen: set[Key] = set()
    stack = [start]
    while stack:
        key = stack.pop()
        if key in seen:
            continue
        seen.add(key)
        module = key[0]
        for name in calls(NODES[key]):
            found = resolve(module, name)
            if found is not None:
                stack.append(found)
    return seen


def unbounded(node: ast.AST) -> int:
    return sum(
        isinstance(sub, ast.While)
        and isinstance(sub.test, ast.Constant)
        and sub.test.value is True
        for sub in ast.walk(node)
    )


#: module -> its source lines, for reading the pragma beside a raise.
LINES: dict[str, list[str]] = {}
for info in pkgutil.iter_modules(boolean.__path__):
    if info.name != "examples":
        LINES[info.name] = inspect.getsource(
            importlib.import_module(f"{PACKAGE}.{info.name}")
        ).splitlines()


def raised(module: str, node: ast.AST) -> set[tuple[str, int, bool]]:
    """Raise sites: exception name, line, and whether a pragma calls it dead.

    ``# pragma: no cover`` beside a raise is the code's own claim that the
    site is unreachable -- which is exactly a totality claim, made where
    the guard is.  It can sit on the ``raise`` line or on the closing
    paren of a multi-line one, so the whole statement's span is scanned.
    """
    out: set[tuple[str, int, bool]] = set()
    src = LINES[module]
    for sub in ast.walk(node):
        if isinstance(sub, ast.Raise) and sub.exc is not None:
            target = sub.exc.func if isinstance(sub.exc, ast.Call) else sub.exc
            if not isinstance(target, ast.Name):
                continue
            span = src[sub.lineno - 1 : (sub.end_lineno or sub.lineno)]
            out.add(
                (target.id, sub.lineno, any("pragma: no cover" in s for s in span))
            )
    return out


HELPERS = {
    "decision_tree_tokens": "tree",
    "decision_tree_program": "tree",
    "minterm_sum": "rows",
    "best_input_order": "order",
    "_greedy_input_order": "order",
    "essential_inputs": "fold",
    "_maybe_complement": "fold",
}
GENERATORS = set(BY_BOOLEAN)

groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
loop_sites: dict[str, list[str]] = defaultdict(list)

for name in sorted(BY_BOOLEAN):
    fn = getattr(boolean, name)
    module = fn.__module__.rsplit(".", 1)[-1]
    where = reach((module, fn.__name__))
    loops = sorted({f"{m}.{f}" for m, f in where if unbounded(NODES[m, f])})
    sites: set[tuple[str, str, int, bool]] = set()
    tags: set[str] = set()
    embeds: set[str] = set()
    for key in where:
        sites |= {(key[0], *site) for site in raised(key[0], NODES[key])}
        for called in calls(NODES[key]):
            if called in HELPERS:
                tags.add(HELPERS[called])
            if called in GENERATORS and called != fn.__name__:
                embeds.add(called)
    sites = {s for s in sites if s[1] != "AttributeError"}
    live = sorted({exc for _, exc, _, dead in sites if not dead})
    guarded = sorted({exc for _, exc, _, dead in sites if dead})
    for site in loops:
        loop_sites[site].append(name)
    print(
        f"{name:24} {module:22} {len(where):3} fns  "
        f"{','.join(sorted(tags)) or '-':<18} "
        f"embeds={','.join(sorted(embeds)) or '-':<12} "
        f"loops={len(loops)}  "
        f"live={','.join(live) or '-':<44} "
        f"dead={','.join(guarded) or '-'}"
    )
    groups[tuple(live)].append(name)

print("\n== by raise set ==")
for key, names in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    print(f"[{','.join(key) or 'no raise'}] {len(names)}: {' '.join(names)}")

print("\n== unbounded loop sites, and who reaches them ==")
for site, names in sorted(loop_sites.items()):
    print(f"{site}: {' '.join(names)}")
