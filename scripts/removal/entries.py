"""Cut a language's entries out of the shared Python tables.

The source-cutting phase of ``remove_language``: entries in dicts, lists
and shared modules are located by AST and cut by line or by column, and
top-level definitions nothing surviving names are dropped as dead code.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).parents[2]
# scripts/ holds the sibling `removal` package, like `verify` and `docs`.
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from removal.ownership import _gone  # noqa: E402


def _outermost(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Return the distinct spans no other span contains."""
    return [
        span
        for span in set(spans)
        if not any(o != span and o[0] <= span[0] and span[1] <= o[1] for o in spans)
    ]


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


def _drop_entries(  # noqa: C901
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
    # ``_JAUNE_LANGUAGE`` in the ``_LANGUAGES`` tuple: an item that is only a
    # name imported from a deleted module, which would otherwise keep its
    # import alive.
    imported = {
        alias.asname or alias.name
        for node in parsed.body
        if isinstance(node, ast.ImportFrom) and _gone(node.module, modules)
        for alias in node.names
    }
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
                if (
                    named(item)
                    or named(first)
                    or (isinstance(item, ast.Name) and item.id in imported)
                ):
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
    dead = imported | {
        node.name
        for node in parsed.body
        if isinstance(node, ast.FunctionDef | ast.ClassDef)
        and any(lo <= node.lineno <= hi for lo, hi in spans)
    }
    while True:
        spanned = {lo for lo, _ in spans}
        more = [
            node
            for node in parsed.body
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
    spans = _outermost(spans)
    # An import another language still uses stays (Cyclic tag reuses BCT's
    # PAIR); judged on the source with every other cut already made.
    imports = {
        node.end_lineno or node.lineno: node
        for node in parsed.body
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


def _drop_matching_items(
    path: Path,
    extract: Callable[
        [ast.AST, Callable[[ast.AST], tuple[int, int]]],
        tuple[list[tuple[int, int, str | None]], bytes] | None,
    ],
    wanted: set[str],
) -> int:
    """Cut each container item whose value is in ``wanted``, one per pass.

    ``extract(node, span)`` returns the ``(lo, hi, value)`` items and the
    empty-container spelling for a node it recognizes, else None.  One cut
    per pass because the byte offsets shift after each write.
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
            extracted = extract(node, span)
            if extracted is None:
                continue
            items, empty = extracted
            for i, (lo, hi, value) in enumerate(items):
                if value not in wanted:
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


def _str_value(node: ast.AST) -> str | None:
    """Return the node's value if it is a string constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


#: How each container spells itself once every item is cut.

_EMPTY = {ast.List: b"[]", ast.Set: b"set()", ast.Tuple: b"()"}


def _container_items(
    node: ast.AST,
    span: Callable[[ast.AST], tuple[int, int]],
    value_of: Callable[[ast.AST], str | None],
    sequences: tuple[type[ast.AST], ...],
) -> tuple[list[tuple[int, int, str | None]], bytes] | None:
    """Extract ``(start, end, value)`` items from a dict or one of ``sequences``.

    Returns the items and the container's empty spelling, or None for any
    other node or a dict with a ``**`` entry.
    """
    if isinstance(node, ast.Dict) and None not in node.keys:
        items = [
            (span(k)[0], span(v)[1], value_of(k))
            for k, v in zip(node.keys, node.values, strict=True)
            if k is not None
        ]
        return items, b"{}"
    if isinstance(node, ast.List | ast.Set | ast.Tuple) and isinstance(node, sequences):
        items = [(*span(e), value_of(e)) for e in node.elts]
        return items, _EMPTY[type(node)]
    return None


def _inline_items(
    node: ast.AST, span: Callable[[ast.AST], tuple[int, int]]
) -> tuple[list[tuple[int, int, str | None]], bytes] | None:
    """Extract string-constant items from a dict, list, set, or tuple."""
    return _container_items(node, span, _str_value, (ast.List, ast.Set, ast.Tuple))


def _drop_inline_items(path: Path, keys: set[str]) -> int:
    """Cut each item keyed by ``keys`` that shares its line with others.

    ``frozenset({"A Painter Ant", "Suffolk"})`` holds two languages on one
    line, which :func:`_drop_entries` leaves.  Cut by column instead, with
    the separating comma; a container left empty is spelled empty.
    """
    return _drop_matching_items(path, _inline_items, keys)


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
    spans = _outermost(spans)
    for lo, hi in sorted(spans, reverse=True):
        del lines[lo - 1 : hi]
    path.write_text("".join(lines), encoding="utf-8")
    return len(spans)
