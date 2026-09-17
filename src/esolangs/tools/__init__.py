"""Boolean-function program generators and shared generation helpers."""

from esolangs.tools.algebraic_programming_language import algebraic_programming_language
from esolangs.tools.alight import alight
from esolangs.tools.b_tapemark import b_tapemark
from esolangs.tools.circuit_diagram import circuit_diagram
from esolangs.tools.crement import crement
from esolangs.tools.cvnc import cvnc
from esolangs.tools.egl import egl
from esolangs.tools.fargo import fargo
from esolangs.tools.inject import inject
from esolangs.tools.interprogck8 import interprogck8
from esolangs.tools.nopstacle import nopstacle
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
    ztoalc_l,
)
from esolangs.tools.packlang import packlang
from esolangs.tools.parameterized import (
    a_painter_ant,
    arrowqueue,
    back,
    bfpda,
    bio,
    bitdeque,
    cod,
    eval,  # noqa: A004 - the language is named "Eval"
    home_row,
    minifuck,
    minsky_swap,
    nocomment,
    one_two_three,
    pct_squared_minus_one,
    ram0,
    wii2d,
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
    circlefuck_byte,
    dimensional,
    dimensional_tree,
    factor,
    jaune,
    jaune_multiply,
    painfuck,
    rotfuck,
    sbleq,
    six_five,
    slow_acv_mammalian,
    suffolk,
    three_d_brainfuck,
)
from esolangs.tools.vandevelo import vandevelo

__all__ = [
    "BOOLEAN",
    "a_painter_ant",
    "addsubjump",
    "algebraic_programming_language",
    "alight",
    "arrowqueue",
    "b_tapemark",
    "back",
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
    "circlefuck_byte",
    "circuit_diagram",
    "clockwise",
    "cod",
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
    "interprogck8",
    "jaune",
    "jaune_multiply",
    "laserfuck",
    "minifuck",
    "minsky_swap",
    "modulous",
    "nocomment",
    "nopstacle",
    "one_two_three",
    "packlang",
    "painfuck",
    "pct_squared_minus_one",
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
    "wii2d",
    "ztoalc_l",
]


def __getattr__(name: str) -> frozenset[str]:
    """Derive ``BOOLEAN`` from the registry on first access."""
    if name != "BOOLEAN":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from esolangs.registry import LANGUAGES

    return frozenset(
        lang.name for lang in LANGUAGES.values() if lang.boolean is not None
    )
