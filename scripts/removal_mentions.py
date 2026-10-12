"""Classify removal hits without hiding uncertain references."""

from __future__ import annotations

import ast
import re
from contextlib import suppress
from pathlib import Path


def mention_edit(root: Path, mention: str, name: str | None = None) -> str:
    """Classify a raw hit without suppressing ambiguous values or fixtures."""
    path, number, text = mention.split(":", 2)
    tree = None
    if path.endswith(".py") and (root / path).is_file():
        # Broken sources still need a visible dependency report.
        with suppress(SyntaxError):
            tree = ast.parse((root / path).read_text(encoding="utf-8"))
    line = int(number)
    calls = (
        [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        if tree is not None
        else []
    )
    if tree is not None and any(
        isinstance(node, ast.Import | ast.ImportFrom)
        and node.lineno <= line <= (node.end_lineno or node.lineno)
        for node in ast.walk(tree)
    ):
        return "code: remove or replace the language dependency"
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            collection, key = node.value, node.slice
            owner = (
                collection.id
                if isinstance(collection, ast.Name)
                else collection.attr
                if isinstance(collection, ast.Attribute)
                else ""
            )
            if (
                owner in {"LANGUAGES", "BY_ID", "WRAPPERS", "INTERPRETERS", "RUNNERS"}
                and isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and name is not None
                and key.value.casefold() == name.casefold()
                and key.lineno <= line <= (key.end_lineno or key.lineno)
            ):
                return "code: remove or replace the language dependency"
    for call in calls:
        function = call.func
        called = (
            function.attr
            if isinstance(function, ast.Attribute)
            else function.id
            if isinstance(function, ast.Name)
            else ""
        )
        if called not in {
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
        }:
            continue
        position = 1 if called in {"wrap_program", "balance_program"} else 0
        arguments = call.args[position : position + 1] + [
            keyword.value for keyword in call.keywords if keyword.arg == "language"
        ]
        if any(
            isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and name is not None
            and arg.value.casefold() == name.casefold()
            and arg.lineno <= line <= (arg.end_lineno or arg.lineno)
            for arg in arguments
        ):
            return "code: remove or replace the language dependency"
    if tree is not None and path == "tests/tooling/scripts/test_new_language.py":
        helpers = {
            "_owner_id",
            "_stale_timing",
            "_drop_bullets",
            "_drop_doc_entries",
            "_mention_edit",
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.lineno <= line <= (node.end_lineno or node.lineno) and any(
                isinstance(part, ast.Attribute)
                and isinstance(part.value, ast.Name)
                and part.value.id == "remove_language"
                and part.attr in helpers
                for part in ast.walk(node)
            ):
                return "fixture: deliberate scanner regression data"
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
        tree is not None
        and any(
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and node.lineno <= line <= (node.end_lineno or node.lineno)
            for node in ast.walk(tree)
        )
    ):
        return "comment: reword or drop the mention"
    if path.endswith((".toml", ".yaml", ".yml", ".json")):
        return "configuration: inspect the remaining reference"
    return "code: inspect the remaining dependency"
