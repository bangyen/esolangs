"""Packlang lexical source wrapping."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from esolangs.generation.wrap import _join_tokens

_PACKLANG_LEXEME = r"[A-Za-z_][A-Za-z_0-9]*|\d+|[{}();:,^!]"


def _packlang(program: str, width: int) -> str:
    """Fold complete Packlang lexical tokens, reducing indent when necessary."""
    lines = []
    for line in program.split("\n"):
        if len(line) <= width:
            lines.append(line)
            continue
        tokens = re.findall(_PACKLANG_LEXEME, line)
        if "".join(tokens) != "".join(line.split()):
            return program
        indent = line[: len(line) - len(line.lstrip())]
        indent = indent[: max(0, width - max(map(len, tokens), default=0))]
        folded = _join_tokens(tokens, max(1, width - len(indent)), separator=" ")
        lines.extend(indent + part for part in folded.split("\n"))
    return "\n".join(lines)


def same_layout(template: str, plain: str, _layout: Callable[[int], Any]) -> bool:
    """Whether only whitespace between lexemes changed."""
    return "".join(template.split()) == "".join(plain.split())
