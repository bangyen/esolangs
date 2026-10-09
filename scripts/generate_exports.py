"""Write ``esolangs.tools``'s generator imports from the ``LANGUAGE`` declarations.

Read statically, never imported: a half-written generator cannot break the
file that registers it.  ``generate.py docs`` runs this, and
``check_generated_docs.py`` holds the committed file to it.
"""

from __future__ import annotations

import ast
import builtins
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
INIT = "src/esolangs/tools/__init__.py"
START = "# BEGIN GENERATED EXPORTS: python scripts/generate.py docs"
END = "# END GENERATED EXPORTS"


def declared(root: pathlib.Path = ROOT) -> list[tuple[str, str]]:
    """Return ``(module, generator)`` for every module declaring a ``LANGUAGE``."""
    tools = root / "src/esolangs/tools"
    found = []
    for path in [*tools.glob("*.py"), *tools.glob("*/__init__.py")]:
        text = path.read_text(encoding="utf-8")
        start = text.find("\nLANGUAGE = Language(")
        if start < 0:
            continue
        statement = ast.parse(text[start:]).body[0]
        assert isinstance(statement, ast.Assign)
        assert isinstance(statement.value, ast.Call)
        generator = next(
            kw.value.id
            for kw in statement.value.keywords
            if kw.arg == "boolean" and isinstance(kw.value, ast.Name)
        )
        module = path.parent.name if path.name == "__init__.py" else path.stem
        found.append((module, generator))
    return sorted(found)


def render(root: pathlib.Path = ROOT) -> str:
    """Return the import block and ``__all__`` for :data:`declared`."""
    pairs = declared(root)
    imports = "\n".join(
        f"from esolangs.tools.{m} import {g}"
        # A generator named for its language may shadow a builtin (Eval).
        + ("  # noqa: A004 - the language's name" if hasattr(builtins, g) else "")
        for m, g in pairs
    )
    names = sorted(["BOOLEAN", *(g for _, g in pairs)])
    listed = "\n".join(f'    "{name}",' for name in names)
    return f"{imports}\n\n__all__ = [\n{listed}\n]"


def update(output_root: pathlib.Path = ROOT, source_root: pathlib.Path = ROOT) -> None:
    """Rewrite the marked block of ``tools/__init__.py`` under ``output_root``."""
    path = output_root / INIT
    text = path.read_text(encoding="utf-8")
    block = START + "\n" + render(source_root) + "\n" + END
    head, rest = text.split(START, 1)
    path.write_text(head + block + rest.split(END, 1)[1], encoding="utf-8")


if __name__ == "__main__":
    update()
