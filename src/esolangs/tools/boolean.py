"""Boolean-function program generators (re-exported from the booleans package).

Each generator builds a program that reads n boolean inputs and prints the
truth-table result for the combination it is given.

The generators live in ``esolangs.tools.booleans``, split by language family
(``register``, ``stack``, ``tape``, ``other``); this module re-exports them
for compatibility.
"""

from esolangs.tools.booleans.other import clockwise, nevermind, taglate, three_x
from esolangs.tools.booleans.register import dig, polynomial, qoibl, sophie
from esolangs.tools.booleans.stack import bfstack, forth, modulous
from esolangs.tools.booleans.tape import (
    ascii_art,
    basicfuck,
    brainif,
    circlefuck,
    circlefuck_byte,
    dimensional,
    six_five,
)

__all__ = [
    "ascii_art",
    "basicfuck",
    "bfstack",
    "brainif",
    "circlefuck",
    "circlefuck_byte",
    "clockwise",
    "dig",
    "dimensional",
    "forth",
    "modulous",
    "nevermind",
    "polynomial",
    "qoibl",
    "six_five",
    "sophie",
    "taglate",
    "three_x",
]
