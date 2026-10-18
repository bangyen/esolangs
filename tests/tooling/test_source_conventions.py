"""Source conventions ruff and mypy cannot see."""

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
TREES = ("src", "scripts", "tests", "checks")

#: Functions excused from ruff's ``max-complexity``.  A refactor that drops
#: a ``noqa: C901`` lowers this; nothing raises it -- split the dispatch by
#: the spec's sections instead (CONTRIBUTING, Code shape).
C901_EXCUSED = 8
_C901 = re.compile(r"#\s*noqa:[^#\n]*\bC901\b")


def _sources() -> dict[str, str]:
    """Return every checked ``.py`` file's text, keyed by repo-relative path."""
    return {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for tree in TREES
        for path in sorted((ROOT / tree).rglob("*.py"))
    }


def test_the_complexity_excuses_only_go_down() -> None:
    """Count every ``noqa: C901``, combined forms included."""
    found = {
        path: hits for path, text in _sources().items() if (hits := _C901.findall(text))
    }
    count = sum(map(len, found.values()))
    assert count <= C901_EXCUSED, (
        f"{count} `noqa: C901`, ceiling {C901_EXCUSED}: split, don't excuse. {found}"
    )
    assert count == C901_EXCUSED, f"{count} left: lower C901_EXCUSED to {count}"


def test_the_complexity_pattern_reads_combined_forms() -> None:
    """Positive control for the ratchet's pattern."""
    noqa = "#" + " noqa"  # split, so the ratchet does not count this file
    assert _C901.search(f"def f():  {noqa}: PLR0912, C901")
    assert _C901.search(f"def f():  {noqa}: C901")
    assert not _C901.search(f"def f():  {noqa}: C9010")
    assert not _C901.search("# C901 is ruff's complexity code")


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _eager_annotations(tree: ast.Module) -> list[ast.expr]:
    """Return the annotations Python 3.12 and 3.13 evaluate when defined.

    Parameter and return annotations, and annotated assignments outside a
    function body; a local variable's annotation is never evaluated.
    """
    found: list[ast.expr] = []

    def visit(node: ast.AST, *, in_function: bool) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = node.args
            for arg in [
                *args.posonlyargs,
                *args.args,
                *args.kwonlyargs,
                *filter(None, (args.vararg, args.kwarg)),
            ]:
                if arg.annotation is not None:
                    found.append(arg.annotation)
            if node.returns is not None:
                found.append(node.returns)
            in_function = True
        elif isinstance(node, ast.AnnAssign) and not in_function:
            found.append(node.annotation)
        for child in ast.iter_child_nodes(node):
            visit(child, in_function=in_function)

    visit(tree, in_function=False)
    return found


def _unguarded(text: str) -> list[str]:
    """Return ``line: name`` for each checking-only name an eager annotation reads."""
    tree = ast.parse(text)
    if any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in tree.body
    ):
        return []
    hidden = {
        (alias.asname or alias.name).split(".")[0]
        for node in tree.body
        if isinstance(node, ast.If) and _is_type_checking(node.test)
        for statement in node.body
        if isinstance(statement, ast.Import | ast.ImportFrom)
        for alias in statement.names
    }
    return [
        f"{name.lineno}: {name.id}"
        for annotation in _eager_annotations(tree)
        for name in ast.walk(annotation)
        if isinstance(name, ast.Name) and name.id in hidden
    ]


def test_checking_only_names_stay_out_of_eager_annotations() -> None:
    """Python 3.14 defers annotations, so a local run hides what 3.12 raises."""
    # Parse only the candidates: all ~1,000 files took 1.45s, past the fast band.
    bad = {
        path: hits
        for path, text in _sources().items()
        if "TYPE_CHECKING" in text and (hits := _unguarded(text))
    }
    assert not bad, (
        f"{bad}: quote the annotation or add `from __future__ import annotations`"
    )


def test_the_annotation_check_catches_each_eager_site() -> None:
    """Positive control: parameters, returns and module annotations are eager."""
    head = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from m import T\n"
    assert _unguarded(head + "def f(x: T): ...") == ["4: T"]
    assert _unguarded(head + "def f() -> list[T]: ...") == ["4: T"]
    assert _unguarded(head + "x: T | None = None") == ["4: T"]
    assert _unguarded(head + "def f(x: 'T'):\n    y: T = x") == []
    assert _unguarded("from __future__ import annotations\n" + head + "x: T") == []


def _control_replacements(text: str) -> list[int]:
    """Return the line of each ``.sub``/``.subn`` replacement holding a control byte."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"sub", "subn"}
        and len(node.args) > 1
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
        and any("\x01" <= char <= "\x08" for char in node.args[1].value)
    ]


def test_regex_replacements_spell_backreferences_raw() -> None:
    """``"\\1"`` without the ``r`` prefix is chr(1), which ruff accepts."""
    bad = {
        path: hits
        for path, text in _sources().items()
        if ".sub" in text and (hits := _control_replacements(text))
    }
    assert not bad, f"{bad}: write the replacement as a raw string"


def test_the_replacement_check_catches_an_octal_escape() -> None:
    """Positive control: chr(1) fires; the raw spelling and a pattern do not."""
    assert _control_replacements('re.sub("(a)", "\\1\\1", s)') == [1]
    assert _control_replacements('re.sub("(a)", r"\\1", s)') == []
    assert _control_replacements('re.sub("\\1", "x", s)') == []
