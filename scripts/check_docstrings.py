"""Check every interpreter docstring against the documented conventions.

Each interpreter module (``src/esolangs/interpreters/*/*.py``) must name the
language it implements and document the behavior it actually exhibits:
EOF handling when it reads input, and the :class:`HaltError` /
:class:`ValueError` cases it raises.  The format is prescribed in
``_template.py``.  Exits nonzero if any interpreter violates the checks, so
the pre-push hook and CI catch a missing or drifted docstring.
"""

import ast
import os
import re
import sys

from esolangs.registry import LANGUAGES

ROOT = os.path.join(os.path.dirname(__file__), os.pardir, "src", "esolangs")
CATEGORIES = ("tape_based", "stack_based", "register_based", "other")


def _norm(text: str) -> str:
    """Lowercase and strip non-alphanumerics for name matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _check(module_path: str, language: str | None) -> list[str]:
    with open(module_path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ["failed to parse"]
    doc = ast.get_docstring(tree) or ""
    issues: list[str] = []
    if len(doc.splitlines()) < 3:
        issues.append("docstring is a bare stub")
    if language is not None and _norm(language) not in _norm(doc):
        issues.append(f"does not name the language ({language!r})")
    if re.search(r"\.input_(char|str|num)\b", source) and "EOF" not in doc:
        issues.append("reads input but does not document EOF")
    if "raise HaltError" in source and "HaltError" not in doc:
        issues.append("raises HaltError but does not document it")
    if "raise ValueError" in source and "ValueError" not in doc:
        issues.append("raises ValueError but does not document it")
    return issues


def main() -> int:
    """Check every interpreter docstring; return a nonzero exit on violations."""
    module_to_name = {
        lang.interpreter: name for name, lang in LANGUAGES.items() if lang.interpreter
    }
    failures = 0
    for category in CATEGORIES:
        directory = os.path.join(ROOT, "interpreters", category)
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            module = f"{category}.{filename[:-3]}"
            path = os.path.join(directory, filename)
            issues = _check(path, module_to_name.get(module))
            if issues:
                failures += 1
                print(f"{module}: " + "; ".join(issues))
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
