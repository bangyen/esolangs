"""Boolean-function program generators (re-exported from the booleans package).

Each generator builds a program that reads n boolean inputs and prints the
truth-table result for the combination it is given.  The parameterized
generators (``bio``, ``back``) instead emit a template the harness
instantiates per input combination, for the no-input languages.

The generators live in ``esolangs.tools.booleans``, split by language family
(``register``, ``stack``, ``tape``, ``other``, ``parameterized``); this
module re-exports them for compatibility.
"""

from esolangs.tools.booleans.other import (
    between,
    clockwise,
    container,
    laserfuck,
    nevermind,
    taglate,
    three_x,
    ztoalc_boolean,
)
from esolangs.tools.booleans.parameterized import back, bio, instantiate, nocomment
from esolangs.tools.booleans.register import (
    collatz_multiverse,
    dig,
    polynomial,
    qoibl,
    sophie,
)
from esolangs.tools.booleans.stack import bfstack, forth, modulous, unsquare
from esolangs.tools.booleans.tape import (
    ascii_art,
    basicfuck,
    bf,
    bf_tree,
    brainif,
    circlefuck,
    circlefuck_byte,
    dimensional,
    dimensional_tree,
    sbleq,
    six_five,
    six_five_arithmetic,
    three_d_bf,
)

__all__ = [
    "ascii_art",
    "back",
    "basicfuck",
    "between",
    "bf",
    "bf_tree",
    "bfstack",
    "bio",
    "brainif",
    "circlefuck",
    "circlefuck_byte",
    "clockwise",
    "collatz_multiverse",
    "container",
    "dig",
    "dimensional",
    "dimensional_tree",
    "forth",
    "instantiate",
    "laserfuck",
    "modulous",
    "nevermind",
    "nocomment",
    "polynomial",
    "qoibl",
    "sbleq",
    "six_five",
    "six_five_arithmetic",
    "sophie",
    "taglate",
    "three_d_bf",
    "three_x",
    "unsquare",
    "ztoalc_boolean",
]
