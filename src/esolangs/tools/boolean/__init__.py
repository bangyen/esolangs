"""Boolean-function program generators (re-exported from the boolean package).

Each generator builds a program that reads n boolean inputs and prints the
truth-table result for the combination it is given; the input count ``n``
is implied by the table length (``2**n`` entries), so the generators take
only the table.  The parameterized generators -- everything re-exported
from ``parameterized`` below, such as ``bio``, ``back``, ``nocomment`` and
``bfpda`` -- instead emit a template the harness instantiates per input
combination.

The generators live in ``esolangs.tools.boolean``, split by language family
(``register``, ``stack``, ``tape``, ``other``, ``parameterized``); this
module re-exports them for compatibility.
"""

from esolangs.tools.boolean.algebraic_programming_language import (
    algebraic_programming_language,
)
from esolangs.tools.boolean.circuit_diagram import circuit_diagram
from esolangs.tools.boolean.cvnc import cvnc
from esolangs.tools.boolean.fargo import fargo
from esolangs.tools.boolean.inject import inject
from esolangs.tools.boolean.other import (
    between,
    bit_tilde,
    clockwise,
    container,
    flowchart,
    forbin_boolean,
    laserfuck,
    myscript,
    nevermind,
    streetcode,
    suptiftam,
    taglate,
    three_x,
    ztoalc_l_boolean,
)
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
    slow_acv_mammalian_boolean,
    suffolk,
    three_d_brainfuck,
)

__all__ = [
    "BOOLEAN",
    "a_painter_ant",
    "addsubjump",
    "algebraic_programming_language",
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
    "eval",
    "factor",
    "fargo",
    "flowchart",
    "forbin_boolean",
    "forth",
    "grapheme",
    "home_row",
    "inject",
    "instantiate",
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
    "painfuck",
    "pct_squared_minus_one",
    "point_break",
    "polynomial",
    "qoibl",
    "ram0",
    "rotfuck",
    "sbleq",
    "six_five",
    "slow_acv_mammalian_boolean",
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
    "ztoalc_l_boolean",
]


def __getattr__(name: str) -> frozenset[str]:
    """Derive ``BOOLEAN`` from the registry on first access.

    Display names of the languages that have a boolean-function generator,
    used by the capability matrix and the public API's ``describe``.

    This is computed from :data:`~esolangs.registry.LANGUAGES` rather than
    listed, so it cannot fall out of step with what the package actually
    provides -- the failure it used to allow was silent, since a generator
    missing from a hand-written set still worked while ``describe``
    reported it absent.  ``text_generator`` has always been derived this
    way (``lang.text is not None``); this puts the boolean side on the
    same footing.

    The lookup is lazy because :mod:`esolangs.registry` imports this
    package to reference the generators, so it cannot be imported at module
    scope here.  The same reason ``tools.text`` imports the registry inside
    its ``main``.
    """
    if name != "BOOLEAN":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from esolangs.registry import LANGUAGES

    return frozenset(
        lang.name for lang in LANGUAGES.values() if lang.boolean is not None
    )
