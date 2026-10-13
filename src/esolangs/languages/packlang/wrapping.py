"""Packlang lexical source wrapping."""

from __future__ import annotations

import re

from esolangs.generation.wrap import _join_tokens
from esolangs.languages.packlang.interpreter._lex import _TOKEN

#: The lexer's own token grammar, so a wrap never splits a token.
_PACKLANG_LEXEME = _TOKEN.pattern


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
