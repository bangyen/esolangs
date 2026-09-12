r"""Boolean-function program generators (re-exported from the boolean."""

from esolangs.tools.boolean.algebraic_programming_language import (
    algebraic_programming_language,
)
from esolangs.tools.boolean.alight import alight
from esolangs.tools.boolean.circuit_diagram import circuit_diagram
from esolangs.tools.boolean.cvnc import cvnc
from esolangs.tools.boolean.fargo import fargo
from esolangs.tools.boolean.inject import inject
from esolangs.tools.boolean.interprogck8 import interprogck8
from esolangs.tools.boolean.other import (
    between,
    bit_tilde,
    clockwise,
    container,
    dinac,
    flowchart,
    forbin,
    function_x_y,
    laserfuck,
    myscript,
    nevermind,
    streetcode,
    suptiftam,
    taglate,
    three_x,
    ztoalc_l,
)
from esolangs.tools.boolean.packlang import packlang
from esolangs.tools.boolean.parameterized import (
    a_painter_ant,
    arrowqueue,
    back,
    bfpda,
    bio,
    bitdeque,
    cod,
    eval,  # noqa: A004 - the language is named "Eval"
    home_row,
    instantiate,
    lamfunc,
    minifuck,
    minsky_swap,
    nocomment,
    one_two_three,
    pct_squared_minus_one,
    ram0,
    wii2d,
)
from esolangs.tools.boolean.register import (
    addsubjump,
    collatz_multiverse,
    decleq,
    dig,
    point_break,
    polynomial,
    qoibl,
    sophie,
)
from esolangs.tools.boolean.stack import bfstack, forth, grapheme, modulous, unsquare
from esolangs.tools.boolean.super_snusp import super_snusp
from esolangs.tools.boolean.tape import (
    basicfuck,
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

__all__ = [
    "BOOLEAN",
    "a_painter_ant",
    "addsubjump",
    "algebraic_programming_language",
    "alight",
    "arrowqueue",
    "back",
    "basicfuck",
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
    "cvnc",
    "decleq",
    "dig",
    "dimensional",
    "dimensional_tree",
    "dinac",
    "eval",
    "factor",
    "fargo",
    "flowchart",
    "forbin",
    "forth",
    "function_x_y",
    "grapheme",
    "home_row",
    "inject",
    "instantiate",
    "interprogck8",
    "jaune",
    "jaune_multiply",
    "lamfunc",
    "laserfuck",
    "minifuck",
    "minsky_swap",
    "modulous",
    "myscript",
    "nevermind",
    "nocomment",
    "one_two_three",
    "packlang",
    "painfuck",
    "pct_squared_minus_one",
    "point_break",
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
    "suptiftam",
    "taglate",
    "three_d_brainfuck",
    "three_x",
    "unsquare",
    "wii2d",
    "ztoalc_l",
]


def __getattr__(name: str) -> frozenset[str]:
    r"""Derive ``BOOLEAN`` from the registry on first access."""
    if name != "BOOLEAN":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from esolangs.registry import LANGUAGES

    return frozenset(
        lang.name for lang in LANGUAGES.values() if lang.boolean is not None
    )
