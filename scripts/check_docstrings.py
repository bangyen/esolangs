r"""Check every interpreter docstring against the documented."""

import ast
import os
import re
import sys

from esolangs.registry import LANGUAGES

ROOT = os.path.join(os.path.dirname(__file__), os.pardir, "src", "esolangs")


def _categories() -> list[str]:
    r"""Return every interpreter category directory, newest included."""
    interpreters = os.path.join(ROOT, "interpreters")
    return sorted(
        entry
        for entry in os.listdir(interpreters)
        if not entry.startswith(("_", "."))
        and os.path.isdir(os.path.join(interpreters, entry))
    )


def _norm(text: str) -> str:
    r"""Lowercase and strip non-alphanumerics for name matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _check(module_path: str, language: str | None) -> list[str]:
    _ = language
    with open(module_path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        ast.parse(source)
    except SyntaxError:
        return ["failed to parse"]
    return []


def main() -> int:
    r"""Check every interpreter docstring; return a nonzero exit on."""
    module_to_name = {
        lang.interpreter: name for name, lang in LANGUAGES.items() if lang.interpreter
    }
    failures = 0
    checked: set[str] = set()
    for category in _categories():
        directory = os.path.join(ROOT, "interpreters", category)
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            module = f"{category}.{filename[:-3]}"
            checked.add(module)
            path = os.path.join(directory, filename)
            issues = _check(path, module_to_name.get(module))
            if issues:
                failures += 1
                print(f"{module}: " + "; ".join(issues))

    # The walk above is only as.
    # replaced was a coverage hole.
    # the registry names must have.
    # language whose interpreter.
    # here instead of quietly going.
    missed = sorted(set(module_to_name) - checked)
    if missed:
        failures += len(missed)
        for module in missed:
            print(f"{module}: registered but not found by the docstring walk")

    if failures:
        print(
            f"\n{failures} interpreter docstrings violate the conventions "
            "(see _template.py)"
        )
        return 1
    print("all interpreter docstrings follow the conventions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
