"""Write the repository's hand-edited TOML: readable strings, stable layout.

``tomllib`` reads TOML but nothing in the standard library writes it.  This
covers the shapes the fixtures use: scalars, string lists, inline tables of
scalars, and arrays of tables.  Long prose folds at spaces with a
line-ending backslash; multi-line text becomes a literal block, so programs
read exactly as written.
"""

from __future__ import annotations

import json
import re

WIDTH = 88
_BARE = re.compile(r"[A-Za-z0-9_-]+")
# Characters a literal string cannot hold, besides the closing quotes.
_ILLEGAL_LITERAL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def key(name: str) -> str:
    """Return ``name`` bare when TOML allows it, else quoted."""
    return name if _BARE.fullmatch(name) else _basic(name)


def _basic(text: str) -> str:
    """Return ``text`` as a one-line basic string."""
    # JSON escapes are TOML escapes; TOML also forbids a raw DEL.
    return json.dumps(text, ensure_ascii=False).replace("\x7f", "\\u007f")


def _string(text: str, indent: int) -> str:
    """Return ``text`` as the most readable string that parses back exactly."""
    literal = "\n" in text and not _ILLEGAL_LITERAL.search(text)
    if literal and "'''" not in text and not text.endswith("'"):
        return "'''\n" + text + "'''"
    one = _basic(text)
    if indent + len(one) <= WIDTH or "\n" in text or "  " in text:
        return one
    # Fold at spaces: a line-ending backslash drops the newline and the
    # next line's indent, so each piece keeps its own trailing space.
    body = one[1:-1]
    lines, line = [], ""
    for word in body.split(" "):
        if line and len(line) + len(word) + 7 > WIDTH:
            lines.append(line)
            line = ""
        line += word + " "
    lines.append(line[:-1])
    return '"""\\\n' + "\\\n".join("    " + item for item in lines) + '"""'


def value(item: object, indent: int = 0) -> str:
    """Return ``item`` as a TOML value."""
    if isinstance(item, bool):
        return "true" if item else "false"
    if isinstance(item, int):
        return str(item)
    if isinstance(item, str):
        return _string(item, indent)
    if isinstance(item, list):
        parts = [value(part) for part in item]
        flat = "[" + ", ".join(parts) + "]"
        if indent + len(flat) <= WIDTH:
            return flat
        return "[\n" + "".join(f"    {part},\n" for part in parts) + "]"
    if isinstance(item, dict):
        return (
            "{ " + ", ".join(f"{key(k)} = {value(v)}" for k, v in item.items()) + " }"
        )
    raise TypeError(f"cannot write {type(item).__name__}")


def _pairs(table: dict[str, object]) -> list[str]:
    """Return ``key = value`` lines for a table's non-array-of-table entries."""
    return [
        f"{key(k)} = {value(v, len(key(k)) + 3)}"
        for k, v in table.items()
        if not _tables(v)
    ]


def _tables(item: object) -> bool:
    """Say whether ``item`` is written as an array of tables."""
    return isinstance(item, list) and bool(item) and isinstance(item[0], dict)


def dumps(data: dict[str, object]) -> str:
    """Return ``data`` as TOML; nested dicts of dicts become a ``[section]``."""
    blocks = []
    head = []
    for name, item in data.items():
        if isinstance(item, dict) and all(isinstance(v, dict) for v in item.values()):
            blocks.append("\n".join([f"[{key(name)}]", *_pairs(item)]))
        elif _tables(item):
            assert isinstance(item, list)
            blocks.extend("\n".join([f"[[{key(name)}]]", *_pairs(row)]) for row in item)
        else:
            head.extend(_pairs({name: item}))
    if head:
        blocks.insert(0, "\n".join(head))
    return "\n\n".join(blocks) + "\n"
