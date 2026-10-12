"""Boolean generators exported from their language implementations."""

# BEGIN GENERATED EXPORTS: python scripts/docs/generate.py docs
from esolangs.languages.a_painter_ant.generator import a_painter_ant
from esolangs.languages.addsubjump.generator import addsubjump
from esolangs.languages.algebraic_programming_language.generator import (
    algebraic_programming_language,
)
from esolangs.languages.alight.generator import alight
from esolangs.languages.arrowqueue.generator import arrowqueue
from esolangs.languages.b_tapemark.generator import b_tapemark
from esolangs.languages.back.generator import back
from esolangs.languages.befunge.generator import befunge
from esolangs.languages.bf_pda.generator import bfpda
from esolangs.languages.bfstack.generator import bfstack
from esolangs.languages.bio.generator import bio
from esolangs.languages.bit_tilde.generator import bit_tilde
from esolangs.languages.bitdeque.generator import bitdeque
from esolangs.languages.bitwise_cyclic_tag.generator import bitwise_cyclic_tag
from esolangs.languages.boolfuck.generator import boolfuck
from esolangs.languages.brainfuck.generator import brainfuck
from esolangs.languages.brainif.generator import brainif
from esolangs.languages.circlefuck.generator import circlefuck
from esolangs.languages.circuit_diagram.generator import circuit_diagram
from esolangs.languages.clockwise.generator import clockwise
from esolangs.languages.collatz_multiverse.generator import collatz_multiverse
from esolangs.languages.container.generator import container
from esolangs.languages.crement.generator import crement
from esolangs.languages.cvnc.generator import cvnc
from esolangs.languages.cyclic_tag.generator import cyclic_tag
from esolangs.languages.decleq.generator import decleq
from esolangs.languages.dig.generator import dig
from esolangs.languages.dimensional.generator import dimensional
from esolangs.languages.egl.generator import egl
from esolangs.languages.eval.generator import eval  # noqa: A004 - the language's name
from esolangs.languages.factor.generator import factor
from esolangs.languages.false.generator import false
from esolangs.languages.fargo.generator import fargo
from esolangs.languages.fish.generator import fish
from esolangs.languages.flowchart.generator import flowchart
from esolangs.languages.forbin.generator import forbin
from esolangs.languages.forth.generator import forth
from esolangs.languages.fractran.generator import fractran
from esolangs.languages.grapheme.generator import grapheme
from esolangs.languages.home_row.generator import home_row
from esolangs.languages.inject.generator import inject
from esolangs.languages.intercal.generator import intercal
from esolangs.languages.jaune.generator import jaune
from esolangs.languages.laserfuck.generator import laserfuck
from esolangs.languages.line.generator import line
from esolangs.languages.malbolge.generator import malbolge
from esolangs.languages.minifuck.generator import minifuck
from esolangs.languages.minsky_swap.generator import minsky_swap
from esolangs.languages.modulous.generator import modulous
from esolangs.languages.nocomment.generator import nocomment
from esolangs.languages.one_two_three.generator import one_two_three
from esolangs.languages.packlang.generator import packlang
from esolangs.languages.painfuck.generator import painfuck
from esolangs.languages.piet.generator import piet
from esolangs.languages.piet_plus_plus.generator import piet_plus_plus
from esolangs.languages.polynomial.generator import polynomial
from esolangs.languages.qoibl.generator import qoibl
from esolangs.languages.ram0.generator import ram0
from esolangs.languages.rotfuck.generator import rotfuck
from esolangs.languages.sbleq.generator import sbleq
from esolangs.languages.six_five.generator import six_five
from esolangs.languages.slashes.generator import slashes
from esolangs.languages.slow_acv_mammalian.generator import slow_acv_mammalian
from esolangs.languages.smallfuck.generator import smallfuck
from esolangs.languages.smu.generator import smu
from esolangs.languages.sophie.generator import sophie
from esolangs.languages.sstack.generator import sstack
from esolangs.languages.streetcode.generator import streetcode
from esolangs.languages.subleq.generator import subleq
from esolangs.languages.suffolk.generator import suffolk
from esolangs.languages.super_snusp.generator import super_snusp
from esolangs.languages.taglate.generator import taglate
from esolangs.languages.thisthat.generator import thisthat
from esolangs.languages.three_x.generator import three_x
from esolangs.languages.thue.generator import thue
from esolangs.languages.unary.generator import unary
from esolangs.languages.underload.generator import underload
from esolangs.languages.unlambda.generator import unlambda
from esolangs.languages.unsquare.generator import unsquare
from esolangs.languages.vandevelo.generator import vandevelo

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
    "bfpda",
    "bfstack",
    "bio",
    "bit_tilde",
    "bitdeque",
    "bitwise_cyclic_tag",
    "boolfuck",
    "brainfuck",
    "brainif",
    "circlefuck",
    "circuit_diagram",
    "clockwise",
    "collatz_multiverse",
    "container",
    "crement",
    "cvnc",
    "cyclic_tag",
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
    "piet_plus_plus",
    "polynomial",
    "qoibl",
    "ram0",
    "rotfuck",
    "sbleq",
    "six_five",
    "slashes",
    "slow_acv_mammalian",
    "smallfuck",
    "smu",
    "sophie",
    "sstack",
    "streetcode",
    "subleq",
    "suffolk",
    "super_snusp",
    "taglate",
    "thisthat",
    "three_x",
    "thue",
    "unary",
    "underload",
    "unlambda",
    "unsquare",
    "vandevelo",
]
# END GENERATED EXPORTS

BOOLEAN: frozenset[str]


def __getattr__(name: str) -> frozenset[str]:
    """Derive ``BOOLEAN`` from the registry on first access."""
    if name != "BOOLEAN":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from esolangs.registry import LANGUAGES

    return frozenset(
        lang.name for lang in LANGUAGES.values() if lang.boolean is not None
    )
