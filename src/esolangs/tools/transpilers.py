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
    "bfstack_to_bf",
    "nocomment_to_bf",
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


def _auto_size(ops: list[str]) -> int:
    """Compute the smallest data region that contains the program's pointer.

    Walks the filtered commands tracking the pointer's minimum and maximum
    reach.  A loop whose body returns to its entry pointer (net-zero
    displacement) can never drift the pointer, so its reach is bounded by
    the body's own excursions regardless of how many times it runs.  The
    empty program needs one cell.
    """
    stack: list[int] = []
    match: dict[int, int] = {}
    for i, c in enumerate(ops):
        if c == "[":
            stack.append(i)
        elif c == "]" and stack:
            j = stack.pop()
            match[i] = j
            match[j] = i

    def scan(i: int, end: int, p: int) -> tuple[int, int, int, bool]:
        lo = hi = p
        while i < end:
            c = ops[i]
            if c == ">":
                p += 1
                hi = max(hi, p)
            elif c == "<":
                p -= 1
                lo = min(lo, p)
            elif c == "[":
                j = match.get(i)
                if j is None or j >= end:
                    break  # unmatched bracket: CircleFuck halts on it
                blo, bhi, bend, ok = scan(i + 1, j, p)
                if not ok:
                    return (lo, hi, p, False)
                hi = max(hi, bhi)
                lo = min(lo, blo)
                if bend != p:
                    return (lo, hi, p, False)
                i = j + 1
                continue
            i += 1
        return (lo, hi, p, True)

    lo, hi, _, ok = scan(0, len(ops), 0)
    if lo < 0:
        raise ValueError(
            "the program moves its data pointer below cell 0, where brainfuck "
            "clamps but CircleFuck's tape wraps around"
        )
    if not ok:
        raise ValueError(
            "the program has a loop that drifts the data pointer without bound; "
            "pass size explicitly if the program stays within [0, size)"
        )
    return hi + 1


def bf_to_circlefuck(program: str, size: int | None = None) -> str:
    """Rewrite a brainfuck program into CircleFuck.

    CircleFuck's tape is the program itself, so a clean data region must be
    set up first.  Each of the ``size`` data cells holds ``>`` -- the only
    command whose value (62) is not a bracket -- so the setup walk can move
    past them and zero each with an exact run of ``-``s without ever writing
    a ``[``/``]`` character (CircleFuck's bracket matching reads the current
    cell values, so a zeroed ``[`` would no longer be a bracket).  The
    brainfuck commands then follow unchanged: CircleFuck's ``[``/``]``
    already test the cell at the data pointer.  ``@`` halts.

    The data pointer must stay within ``[0, size)``: moving below cell 0
    wraps around to the end of the program (where brainfuck clamps), and
    moving past cell ``size - 1`` enters the setup code.  When ``size`` is
    omitted it is computed from the program: the smallest bound that holds
    for every loop whose body has net-zero pointer displacement.  Programs
    with loops that drift the pointer, or that move below cell 0, are
    rejected rather than silently mistranslated; pass ``size`` explicitly to
    cover a program you know stays in bounds.
    """
    ops = [c for c in program if c in "+-<>.,[]"]
    if size is None:
        size = _auto_size(ops)
    if size < 1:
        raise ValueError(f"size must be positive, got {size}")
    setup = ">" * size + ("<" + "-" * 62) * size
    return setup + "".join(ops) + "@"


_NOCOMMENT_TO_BF = {"c": "[-]", "i": "+", "o": "."}


def nocomment_to_bf(program: str) -> str:
    """Rewrite a NoComment program into brainfuck.

    NoComment is a strict subset of brainfuck: ``c`` clears the current
    cell (``[-]``), ``i`` increments it (``+``), and ``o`` prints it as a
    byte (``.``).  Anything else is a comment and is dropped.
    """
    return "".join(_NOCOMMENT_TO_BF[c] for c in program if c in _NOCOMMENT_TO_BF)


_BFSTACK_TO_BF = {
    ">": ">",
    "<": "[-]<",
    "+": "+",
    "-": "-",
    ".": ".",
    ",": ">,",
    "[": "[",
    "]": "]",
}


def bfstack_to_bf(program: str) -> str:
    """Rewrite a BFStack program into brainfuck.

    BFStack is a stack, modelled on brainfuck's tape with the top of the
    stack at the current cell.  ``>`` pushes a fresh zero cell and stays a
    ``>``; ``<`` pops, but must first clear the cell (``[-]<``) so a later
    push lands on a fresh zero again; ``,`` reads a byte and pushes, so it
    becomes ``>,``.  The remaining commands map directly.  Anything else is
    a comment and is dropped.
    """
    return "".join(_BFSTACK_TO_BF[c] for c in program if c in _BFSTACK_TO_BF)


TRANSPILERS: dict[tuple[str, str], Callable[..., str]] = {
    ("BF", "ASCII art"): bf_to_ascii_art,
    ("ASCII art", "BF"): ascii_art_to_bf,
    ("BF", "CircleFuck"): bf_to_circlefuck,
    ("NoComment", "BF"): nocomment_to_bf,
    ("BFStack", "BF"): bfstack_to_bf,
}
