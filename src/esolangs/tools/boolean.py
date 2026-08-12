"""Boolean-function program generators (re-exported from the booleans package).

Each generator builds a program that reads n boolean inputs and prints the
truth-table result for the combination it is given.

The generators live in ``esolangs.tools.booleans``, split by language family
(``register``, ``stack``, ``tape``, ``other``); this module re-exports them
for compatibility.
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
from esolangs.tools.booleans.register import dig, polynomial, qoibl, sophie
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
    six_five,
    six_five_arithmetic,
)

__all__ = [
    "ascii_art",
    "basicfuck",
    "between",
    "bf",
    "bf_tree",
    "bfstack",
    "brainif",
    "circlefuck",
    "circlefuck_byte",
    "clockwise",
    "container",
    "dig",
    "dimensional",
    "dimensional_tree",
    "forth",
    "laserfuck",
    "modulous",
    "nevermind",
    "polynomial",
    "qoibl",
    "six_five",
    "six_five_arithmetic",
    "sophie",
    "taglate",
    "three_x",
    "unsquare",
    "ztoalc_boolean",
]
