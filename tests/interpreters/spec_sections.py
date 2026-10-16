"""Parse an interpreter spec (its module docstring) into template sections.

The shape is ``src/esolangs/runtime/_template.py``'s own docstring.
"""

import re

#: The optional sections, in the order a spec gives them.
SECTIONS = ("Commands", "Input/output", "Errors", "Decisions")

#: What a caller of ``esolangs.run`` catches; ``Errors:`` names only these.
PUBLIC_ERRORS = frozenset(
    {
        "ProgramError",
        "InputExhaustedError",
        "ArgumentError",
        "HaltError",
        "InterpreterLimitError",
    }
)

_HEADER = re.compile(r"^([A-Z][A-Za-z/ ]*):$")
_ENTRY = re.compile(r"^    (\w+):")


def headers(doc: str) -> list[tuple[int, str]]:
    """Return ``(line index, name)`` for each column-0 ``Name:`` line."""
    return [
        (i, m[1])
        for i, line in enumerate(doc.splitlines())
        if (m := _HEADER.match(line))
    ]


def section(doc: str, name: str) -> list[str]:
    """Return the body lines of section ``name``, or ``[]`` without one."""
    lines = doc.splitlines()
    found = headers(doc)
    for k, (i, header) in enumerate(found):
        if header == name:
            end = found[k + 1][0] if k + 1 < len(found) else len(lines)
            return lines[i + 1 : end]
    return []


def error_entries(doc: str) -> set[str]:
    """Return the exception names ``Errors:`` lists."""
    return {m[1] for line in section(doc, "Errors") if (m := _ENTRY.match(line))}
