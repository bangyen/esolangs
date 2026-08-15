"""Boolean-function program generators (re-exported from the booleans package).

Each generator builds a program that reads n boolean inputs and prints the
truth-table result for the combination it is given.  The parameterized
generators (``bio``, ``back``) instead emit a template the harness
instantiates per input combination, for the no-input languages.

The generators live in ``esolangs.tools.booleans``, split by language family
(``register``, ``stack``, ``tape``, ``other``, ``parameterized``); this
module re-exports them for compatibility.
"""

from esolangs.tools.booleans.abcdirection import abcdirection
from esolangs.tools.booleans.other import (
    between,
    bit_tilde,
    clockwise,
    container,
    forbin_boolean,
    laserfuck,
    myscript,
    nevermind,
    taglate,
    three_x,
    ztoalc_l_boolean,
)
from esolangs.tools.booleans.parameterized import back, bio, instantiate, nocomment
from esolangs.tools.booleans.register import (
    addsubjump,
    collatz_multiverse,
    decleq,
    dig,
    polynomial,
    qoibl,
    sophie,
)
from esolangs.tools.booleans.stack import bfstack, forth, modulous, unsquare
from esolangs.tools.booleans.tape import (
    ascii_art,
    basicfuck,
    bf_tree,
    brainfuck,
    brainif,
    circlefuck,
    circlefuck_byte,
    dimensional,
    dimensional_tree,
    minifuck,
    painfuck,
    sbleq,
    six_five,
    six_five_arithmetic,
    three_d_brainfuck,
)

__all__ = [
    "abcdirection",
    "addsubjump",
    "ascii_art",
    "back",
    "basicfuck",
    "between",
    "bf_tree",
    "bfstack",
    "bio",
    "bit_tilde",
    "brainfuck",
    "brainif",
    "circlefuck",
    "circlefuck_byte",
    "clockwise",
    "collatz_multiverse",
    "container",
    "decleq",
    "dig",
    "dimensional",
    "dimensional_tree",
    "forbin_boolean",
    "forth",
    "instantiate",
    "laserfuck",
    "minifuck",
    "modulous",
    "myscript",
    "nevermind",
    "nocomment",
    "painfuck",
    "polynomial",
    "qoibl",
    "sbleq",
    "six_five",
    "six_five_arithmetic",
    "sophie",
    "taglate",
    "three_d_brainfuck",
    "three_x",
    "unsquare",
    "ztoalc_l_boolean",
]
