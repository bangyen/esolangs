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

__all__ = [
    "TRANSPILERS",
    "ascii_art_to_bf",
    "bf_to_ascii_art",
    "bf_to_circlefuck",
]

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


def bf_to_circlefuck(program: str, size: int = 32) -> str:
    """Rewrite a brainfuck program into CircleFuck.

    CircleFuck's tape is the program itself, so a clean data region must be
    set up first.  Each of the ``size`` data cells holds ``>`` -- the only
    command whose value (62) is not a bracket -- so the setup walk can move
    past them and zero each with an exact run of ``-``s without ever writing
    a ``[``/``]`` character (CircleFuck's bracket matching reads the current
    cell values, so a zeroed ``[`` would no longer be a bracket).  The
    brainfuck commands then follow unchanged: CircleFuck's ``[``/``]``
    already test the cell at the data pointer.  ``@`` halts.

    The source program must keep its data pointer within ``[0, size)``:
    moving below cell 0 wraps around to the end of the program (where
    brainfuck clamps), and moving past cell ``size - 1`` enters the setup
    code.  Most programs use a handful of cells; pass ``size`` explicitly
    when a program uses more.
    """
    if size < 1:
        raise ValueError(f"size must be positive, got {size}")
    ops = [c for c in program if c in "+-<>.,[]"]
    setup = ">" * size + ("<" + "-" * 62) * size
    return setup + "".join(ops) + "@"


TRANSPILERS: dict[tuple[str, str], Callable[..., str]] = {
    ("BF", "ASCII art"): bf_to_ascii_art,
    ("ASCII art", "BF"): ascii_art_to_bf,
    ("BF", "CircleFuck"): bf_to_circlefuck,
}
