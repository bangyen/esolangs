"""Packlang tokenization and position-preserving comment masking."""

import re

from esolangs.interpreters.source_hints import syntax_error


def _strip_comments(code: str, *, preserve_positions: bool = False) -> str:
    """Remove ``%$ ... %`` blocks and ``% ...`` line comments.

    Block comments are taken first: ``%$`` opens one and the next bare
    ``%`` closes it, so a line comment inside a block is part of the block.
    Both are replaced by a space rather than deleted, so ``a%c%b`` cannot
    fuse into one token. ``preserve_positions`` keeps comment widths and newlines.
    """
    out = []
    i = 0
    while i < len(code):
        start = i
        if code.startswith("%$", i):
            end = code.find("%", i + 2)
            i = len(code) if end < 0 else end + 1
            out.append(
                "".join("\n" if c == "\n" else " " for c in code[start:i])
                if preserve_positions
                else " "
            )
        elif code[i] == "%":
            end = code.find("\n", i)
            i = len(code) if end < 0 else end
            out.append(
                "".join("\n" if c == "\n" else " " for c in code[start:i])
                if preserve_positions
                else " "
            )
        else:
            out.append(code[i])
            i += 1
    return "".join(out)


_TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+|[{}();:,^!]")


def _tokenize(code: str) -> list[str]:
    """Return the program's tokens, comments already stripped.

    Any character the pattern does not match is not a Packlang token, so a
    program containing one is malformed -- the fuzz suite's random input is
    exactly that case, and it must raise rather than be silently skipped.
    """
    tokens = _TOKEN.findall(code)
    if "".join(tokens) != "".join(code.split()):
        raise syntax_error(
            "program contains characters that are not Packlang tokens",
            (
                "use identifiers, decimal numbers and {}();:,^! "
                "punctuation; place comments in the supported comment "
                "syntax"
            ),
        )
    return tokens
