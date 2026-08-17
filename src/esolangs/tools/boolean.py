"""Boolean-function program generators (re-exported from the booleans package).

Each generator builds a program that reads n boolean inputs and prints the
truth-table result for the combination it is given; the input count ``n``
is implied by the table length (``2**n`` entries), so the generators take
only the table.  The parameterized generators (``bio``, ``back``,
``nocomment``, ``bfpda``) instead emit a template the harness instantiates
per input combination, for the no-input languages.

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
from esolangs.tools.booleans.parameterized import (
    back,
    bfpda,
    bio,
    bitdeque,
    instantiate,
    lamfunc,
    minsky_swap,
    nocomment,
    ram0,
)
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
    basicfuck,
    bf_tree,
    brainfuck,
    brainif,
    circlefuck,
    circlefuck_byte,
    dimensional,
    dimensional_tree,
    jaune,
    jaune_multiply,
    painfuck,
    rotfuck,
    sbleq,
    six_five,
    six_five_arithmetic,
    three_d_brainfuck,
)

__all__ = [
    "BOOLEAN",
    "abcdirection",
    "addsubjump",
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
    "jaune",
    "jaune_multiply",
    "lamfunc",
    "laserfuck",
    "minsky_swap",
    "modulous",
    "myscript",
    "nevermind",
    "nocomment",
    "painfuck",
    "polynomial",
    "qoibl",
    "ram0",
    "rotfuck",
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

# Display names of the languages that have a boolean-function generator.
# Single source of truth for the capability matrix and the public API's
# ``describe``.
BOOLEAN: frozenset[str] = frozenset(
    {
        "3x",
        "ABCDirection",
        "AddSubJump",
        "3D Brainfuck",
        "6-5",
        "Back",
        "Basicfuck",
        "Between",
        "BF-PDA",
        "Bitdeque",
        "brainfuck",
        "BFStack",
        "BIO",
        "bit~",
        "BrainIf",
        "Circlefuck",
        "Clockwise",
        "Collatz Multiverse",
        "Container",
        "Dig",
        "Dimensional",
        "Decleq",
        "Forbin",
        "Forþ",
        "Jaune",
        "Lamfunc",
        "LaserFuck",
        "Minsky Swap",
        "Modulous",
        "MyScript",
        "Nevermind",
        "NoComment",
        "Painfuck",
        "Polynomial",
        "Qoibl",
        "RAM0",
        "ROTfuck",
        "S*bleq",
        "Sophie",
        "Taglate",
        "Unsquare",
        "ZTOALC L",
    }
)
