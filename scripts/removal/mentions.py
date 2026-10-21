"""Classify removal hits without hiding uncertain references."""

from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
from contextlib import suppress
from pathlib import Path

#: Registries a language's name indexes.
_REGISTRIES = frozenset({"LANGUAGES", "BY_ID", "WRAPPERS", "INTERPRETERS", "RUNNERS"})
#: Calls taking a language name: first argument, or second for the wrappers.
_LANGUAGE_CALLS = frozenset(
    {
        "run",
        "generate",
        "Language",
        "describe",
        "encode_inputs",
        "read_answer",
        "instantiate",
        "resolve",
        "canonical_id",
        "wrap_program",
        "balance_program",
    }
)
_SECOND_ARGUMENT = frozenset({"wrap_program", "balance_program"})
#: Removal helpers whose tests carry language names as scanner fixtures.
_SCANNER_HELPERS = frozenset(
    {
        "_owner_id",
        "_stale_timing",
        "_drop_bullets",
        "_drop_doc_entries",
        "_mention_edit",
    }
)
_DEPENDENCY = "code: remove or replace the language dependency"


def _spans(node: ast.expr | ast.stmt, line: int) -> bool:
    """Whether ``node`` covers ``line``."""
    return node.lineno <= line <= (node.end_lineno or node.lineno)


def _spells(node: ast.expr, name: str | None, line: int) -> bool:
    """Whether ``node`` is a string literal spelling ``name`` and covers ``line``."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and name is not None
        and node.value.casefold() == name.casefold()
        and _spans(node, line)
    )


def _short_name(node: ast.expr) -> str:
    """Return a name's id or an attribute's last part, else the empty string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _parse(root: Path, path: str) -> ast.Module | None:
    """Parse a hit's Python file, or None; broken sources still get a label."""
    if not path.endswith(".py") or not (root / path).is_file():
        return None
    with suppress(SyntaxError):
        return ast.parse((root / path).read_text(encoding="utf-8"))
    return None


def _code_label(tree: ast.Module, path: str, line: int, name: str | None) -> str | None:
    """Classify a hit from the syntax tree alone, or None to fall through."""
    nodes = list(ast.walk(tree))
    if any(
        isinstance(node, ast.Subscript)
        and _short_name(node.value) in _REGISTRIES
        and _spells(node.slice, name, line)
        for node in nodes
    ):
        return _DEPENDENCY
    for call in (node for node in nodes if isinstance(node, ast.Call)):
        called = _short_name(call.func)
        if called not in _LANGUAGE_CALLS:
            continue
        position = 1 if called in _SECOND_ARGUMENT else 0
        arguments = call.args[position : position + 1] + [
            keyword.value for keyword in call.keywords if keyword.arg == "language"
        ]
        if any(_spells(arg, name, line) for arg in arguments):
            return _DEPENDENCY
    if name is not None:
        bindings = {
            alias.asname or alias.name
            for node in nodes
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.split(".", 1)[0] in sys.stdlib_module_names
            for alias in node.names
            if (alias.asname or alias.name).casefold() == name.casefold()
        }
        if bindings and any(
            node.lineno == line
            and (
                (isinstance(node, ast.Name) and node.id in bindings)
                or (
                    isinstance(node, ast.ImportFrom)
                    and any(
                        (alias.asname or alias.name) in bindings for alias in node.names
                    )
                )
            )
            for node in nodes
            if hasattr(node, "lineno")
        ):
            return "identifier: standard-library binding; retain it"
    if any(
        isinstance(node, ast.Import | ast.ImportFrom) and _spans(node, line)
        for node in nodes
    ):
        return _DEPENDENCY
    if (
        name is not None
        and re.fullmatch(r"[0-9]+[a-z]", name)
        and any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.lineno == line
            and re.search(rf"(?<![\w]){re.escape(name)}(?=[\^+ -])", node.value)
            and "=" in node.value
            for node in nodes
        )
    ):
        return "identifier: arithmetic coefficient in source; retain it"
    if path == "tests/tooling/test_new_language.py" and any(
        isinstance(node, ast.FunctionDef)
        and _spans(node, line)
        and any(
            isinstance(part, ast.Attribute)
            and isinstance(part.value, ast.Name)
            and part.value.id == "remove_language"
            and part.attr in _SCANNER_HELPERS
            for part in ast.walk(node)
        )
        for node in nodes
    ):
        return "fixture: deliberate scanner regression data"
    return None


def _in_string_statement(tree: ast.Module, line: int) -> bool:
    """Whether ``line`` is inside a bare string statement, such as a docstring."""
    return any(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        and _spans(node, line)
        for node in ast.walk(tree)
    )


def mention_edit(root: Path, mention: str, name: str | None = None) -> str:
    """Classify a raw hit without suppressing ambiguous values or fixtures."""
    path, number, text = mention.split(":", 2)
    line = int(number)
    tree = _parse(root, path)
    if tree is not None and (label := _code_label(tree, path, line, name)):
        return label
    if (
        name is not None
        and name.casefold().isidentifier()
        and re.search(rf"(['\"`]){re.escape(name.casefold())}\1", text)
    ):
        return "ambiguous: inspect the quoted identifier; keep valid uses"
    if path == "src/esolangs/cli/help.py" or re.search(
        r"\besolangs(?:\s+(?:run|generate|encode|describe|read-answer)\b|\.\w+\()",
        text,
    ):
        return "example: choose a replacement language"
    if path.endswith((".md", ".tex")):
        return "prose: reword or drop the mention"
    if text.lstrip().startswith("#") or (
        tree is not None and _in_string_statement(tree, line)
    ):
        return "comment: reword or drop the mention"
    if path.endswith((".toml", ".yaml", ".yml", ".json")):
        return "configuration: inspect the remaining reference"
    return "code: inspect the remaining dependency"


def drop_owned_comments(path: Path, name: str) -> int:
    """Drop a declared comment cohort when any of its owners is removed."""
    source = path.read_text(encoding="utf-8")
    if "# language-owners:" not in source:
        return 0
    lines = source.splitlines(keepends=True)
    if path.suffix == ".py":
        comments = {
            token.start[0]
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.COMMENT
        }
    else:
        comments = set(range(1, len(lines) + 1))
    removed: set[int] = set()
    for index, line in enumerate(lines):
        if index + 1 not in comments or not line.lstrip().startswith(
            "# language-owners:"
        ):
            continue
        owners = json.loads(line.split("language-owners:", 1)[1])
        if (
            not isinstance(owners, list)
            or not owners
            or not all(isinstance(owner, str) and owner for owner in owners)
        ):
            raise ValueError(f"{path}:{index + 1}: invalid comment owners")
        if name.casefold() not in {owner.casefold() for owner in owners}:
            continue
        stop = index + 1
        while (
            stop < len(lines)
            and lines[stop].lstrip().startswith("#")
            and stop + 1 in comments
            and not lines[stop].lstrip().startswith("# language-owners:")
        ):
            stop += 1
        removed.update(range(index, stop))
    if removed:
        path.write_text(
            "".join(line for i, line in enumerate(lines) if i not in removed),
            encoding="utf-8",
        )
    return len(removed)
