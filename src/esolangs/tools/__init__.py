"""Boolean-function program generators and shared generation helpers."""

from esolangs.tools.addsubjump import addsubjump
from esolangs.tools.algebraic_programming_language import algebraic_programming_language
from esolangs.tools.alight import alight
from esolangs.tools.b_tapemark import b_tapemark
from esolangs.tools.befunge import befunge
from esolangs.tools.bit_tilde import bit_tilde
from esolangs.tools.bitwise_cyclic_tag import bitwise_cyclic_tag
from esolangs.tools.brainfuck import bf_tree, brainfuck
from esolangs.tools.brainif import brainif
from esolangs.tools.circlefuck import circlefuck
from esolangs.tools.circuit_diagram import circuit_diagram
from esolangs.tools.clockwise import clockwise
from esolangs.tools.collatz_multiverse import collatz_multiverse
from esolangs.tools.container import container
from esolangs.tools.crement import crement
from esolangs.tools.cvnc import cvnc
from esolangs.tools.decleq import decleq
from esolangs.tools.dig import dig
from esolangs.tools.dimensional import dimensional
from esolangs.tools.egl import egl
from esolangs.tools.factor import factor
from esolangs.tools.false import false
from esolangs.tools.fargo import fargo
from esolangs.tools.fish import fish
from esolangs.tools.flowchart import flowchart
from esolangs.tools.forbin import forbin
from esolangs.tools.fractran import fractran
from esolangs.tools.inject import inject
from esolangs.tools.intercal import intercal
from esolangs.tools.jaune import jaune
from esolangs.tools.laserfuck import laserfuck
from esolangs.tools.line import line
from esolangs.tools.malbolge import malbolge
from esolangs.tools.packlang import packlang
from esolangs.tools.painfuck import painfuck
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
    underload,
)
from esolangs.tools.piet import piet
from esolangs.tools.polynomial import polynomial
from esolangs.tools.qoibl import qoibl
from esolangs.tools.rotfuck import rotfuck
from esolangs.tools.sbleq import sbleq
from esolangs.tools.six_five import six_five
from esolangs.tools.slow_acv_mammalian import slow_acv_mammalian
from esolangs.tools.smallfuck import smallfuck
from esolangs.tools.sophie import sophie
from esolangs.tools.stack import bfstack, forth, grapheme, modulous, unsquare
from esolangs.tools.streetcode import streetcode
from esolangs.tools.suffolk import suffolk
from esolangs.tools.super_snusp import super_snusp
from esolangs.tools.taglate import taglate
from esolangs.tools.thisthat import thisthat
from esolangs.tools.three_d_brainfuck import three_d_brainfuck
from esolangs.tools.three_x import three_x
from esolangs.tools.thue import thue
from esolangs.tools.unlambda import unlambda
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
    "befunge",
    "bf_tree",
    "bfpda",
    "bfstack",
    "bio",
    "bit_tilde",
    "bitdeque",
    "bitwise_cyclic_tag",
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
    "egl",
    "eval",
    "factor",
    "false",
    "fargo",
    "fish",
    "flowchart",
    "forbin",
    "forth",
    "fractran",
    "grapheme",
    "home_row",
    "inject",
    "intercal",
    "jaune",
    "laserfuck",
    "line",
    "malbolge",
    "minifuck",
    "minsky_swap",
    "modulous",
    "nocomment",
    "one_two_three",
    "packlang",
    "painfuck",
    "piet",
    "polynomial",
    "qoibl",
    "ram0",
    "rotfuck",
    "sbleq",
    "six_five",
    "slow_acv_mammalian",
    "smallfuck",
    "sophie",
    "streetcode",
    "suffolk",
    "super_snusp",
    "taglate",
    "thisthat",
    "three_d_brainfuck",
    "three_x",
    "thue",
    "underload",
    "unlambda",
    "unsquare",
    "vandevelo",
]


def __getattr__(name: str) -> frozenset[str]:
    """Derive ``BOOLEAN`` from the registry on first access."""
    if name != "BOOLEAN":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from esolangs.registry import LANGUAGES

    return frozenset(
        lang.name for lang in LANGUAGES.values() if lang.boolean is not None
    )
