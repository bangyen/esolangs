"""Boolean-function program generators and shared generation helpers."""

from esolangs.tools.algebraic_programming_language import algebraic_programming_language
from esolangs.tools.alight import alight
from esolangs.tools.b_tapemark import b_tapemark
from esolangs.tools.befunge import befunge
from esolangs.tools.circuit_diagram import circuit_diagram
from esolangs.tools.crement import crement
from esolangs.tools.cvnc import cvnc
from esolangs.tools.egl import egl
from esolangs.tools.fargo import fargo
from esolangs.tools.inject import inject
from esolangs.tools.malbolge import malbolge
from esolangs.tools.other import (
    bit_tilde,
    clockwise,
    container,
    flowchart,
    forbin,
    laserfuck,
    streetcode,
    taglate,
    three_x,
)
from esolangs.tools.packlang import packlang
from esolangs.tools.parameterized import (
    a_painter_ant,
    arrowqueue,
    back,
    bfpda,
    bio,
    bitdeque,
    eval,  # noqa: A004 - the language is named "Eval"
    home_row,
    minifuck,
    minsky_swap,
    nocomment,
    one_two_three,
    ram0,
)
from esolangs.tools.register import (
    addsubjump,
    collatz_multiverse,
    decleq,
    dig,
    polynomial,
    qoibl,
    sophie,
)
from esolangs.tools.stack import bfstack, forth, grapheme, modulous, unsquare
from esolangs.tools.super_snusp import super_snusp
from esolangs.tools.tape import (
    bf_tree,
    brainfuck,
    brainif,
    circlefuck,
    dimensional,
    dimensional_tree,
    factor,
    jaune,
    painfuck,
    rotfuck,
    sbleq,
    six_five,
    slow_acv_mammalian,
    suffolk,
    three_d_brainfuck,
)
from esolangs.tools.vandevelo import vandevelo
from esolangs.tools.whitespace import whitespace

__all__ = [
    "BOOLEAN",
    "a_painter_ant",
    "addsubjump",
    "algebraic_programming_language",
    "alight",
    "arrowqueue",
    "b_tapemark",
    "back",
    "befunge",
    "between",
    "bf_tree",
    "bfpda",
    "bfstack",
    "bio",
    "bit_tilde",
    "bitdeque",
    "brainfuck",
    "brainif",
    "circlefuck",
    "circuit_diagram",
    "clockwise",
    "collatz_multiverse",
    "container",
    "crement",
    "cvnc",
    "decleq",
    "dig",
    "dimensional",
    "dimensional_tree",
    "egl",
    "eval",
    "factor",
    "fargo",
    "flowchart",
    "forbin",
    "forth",
    "grapheme",
    "home_row",
    "inject",
    "jaune",
    "laserfuck",
    "malbolge",
    "minifuck",
    "minsky_swap",
    "modulous",
    "nocomment",
    "one_two_three",
    "packlang",
    "painfuck",
    "polynomial",
    "qoibl",
    "ram0",
    "rotfuck",
    "sbleq",
    "six_five",
    "slow_acv_mammalian",
    "sophie",
    "streetcode",
    "suffolk",
    "super_snusp",
    "taglate",
    "three_d_brainfuck",
    "three_x",
    "unsquare",
    "vandevelo",
    "whitespace",
]


def __getattr__(name: str) -> frozenset[str]:
    """Derive ``BOOLEAN`` from the registry on first access."""
    if name != "BOOLEAN":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from esolangs.registry import LANGUAGES

    return frozenset(
        lang.name for lang in LANGUAGES.values() if lang.boolean is not None
    )
