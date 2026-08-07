"""Transpile programs between languages.

Each ``TRANSPILERS`` entry maps a ``(source, target)`` language-name pair to
a function that rewrites a program in the source language into an
equivalent program in the target.  A target is only added when its in-repo
interpreter matches the source language's semantics, so every transpiler is
verified end-to-end: the source runs on its interpreter, the target on its
own, and the outputs must agree.
"""

import importlib
from collections.abc import Callable
from typing import cast

__all__ = ["TRANSPILERS", "ascii_art_to_bf", "bf_to_ascii_art"]

# The eight brainfuck commands -> their ASCII-art blocks.  This is the
# single source of truth for the art alphabet; ``ascii-art.parse`` decodes
# exactly these blocks (by line count and final character).
_BF_ASCII_ART_BLOCKS = {
    "-": "-",
    ".": "#\n#",
    ",": "|\n|\n|",
    "<": "\\\n\\\n\\\n\\",
    ">": "/\n/\n/\n/",
    "+": "|\n|\n|\n|\n|",
    "[": "_\n_\n_\n_\n_\n_",
    "]": "|\n|\n|\n|\n|\n|",
}


def bf_to_ascii_art(program: str) -> str:
    """Rewrite a brainfuck program as ASCII art.

    Each command becomes its art block; anything that is not a brainfuck
    command is dropped.  The empty program stays empty.
    """
    return "\n\n".join(
        _BF_ASCII_ART_BLOCKS[c] for c in program if c in _BF_ASCII_ART_BLOCKS
    )


def ascii_art_to_bf(program: str) -> str:
    """Rewrite an ASCII-art program back to brainfuck.

    This is the ASCII-art interpreter's own decoder: ``ascii-art.parse``
    maps the art blocks to brainfuck commands, so the translation runs
    identically by construction.  Unknown blocks are ignored and the empty
    program stays empty.
    """
    parse = cast(
        Callable[[str], str],
        importlib.import_module("esolangs.interpreters.tape_based.ascii-art").parse,
    )
    return parse(program)


TRANSPILERS: dict[tuple[str, str], Callable[[str], str]] = {
    ("BF", "ASCII art"): bf_to_ascii_art,
    ("ASCII art", "BF"): ascii_art_to_bf,
}
