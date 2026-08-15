"""Text generators (re-exported from the generators package).

The generators live in ``esolangs.tools.generators``, split by language
family; this module re-exports them for compatibility and provides the
``python -m esolangs.tools.generate`` CLI.
"""

import sys

from esolangs.tools.generators.helpers import _ilog
from esolangs.tools.generators.other import (
    basicfuck,
    between,
    bit_tilde,
    clockwise,
    container,
    dimensional,
    forbin,
    forth,
    home_row,
    laserfuck,
    myscript,
    nevermind,
    nocomment,
    one_two_three,
    painfuck,
    pct_squared_minus_one,
    sbleq,
    taglate,
    three_x,
    two_d_fish,
    unsquare,
    ztoalc_l,
)
from esolangs.tools.generators.register import (
    addsubjump,
    albabet,
    bio,
    collatz_multiverse,
    decleq,
    dig,
    dotlang,
    eval,  # noqa: A004 - the language is named "Eval"
    huf,
    polynomial,
    qoibl,
    sophie,
    wii2d,
)
from esolangs.tools.generators.stack import modulous, the_temporary_stack
from esolangs.tools.generators.tape import (
    ascii_art,
    bfstack,
    brainfuck,
    brainif,
    circlefuck,
    excon,
    factor,
    minifuck,
    rotfuck,
    six_five,
    slow_acv_mammalian,
    suffolk,
    three_d_brainfuck,
)

__all__ = [
    "_ilog",
    "addsubjump",
    "albabet",
    "ascii_art",
    "basicfuck",
    "between",
    "bfstack",
    "bio",
    "bit_tilde",
    "brainfuck",
    "brainif",
    "circlefuck",
    "clockwise",
    "collatz_multiverse",
    "container",
    "decleq",
    "dig",
    "dimensional",
    "dotlang",
    "eval",
    "excon",
    "factor",
    "forbin",
    "forth",
    "home_row",
    "huf",
    "laserfuck",
    "minifuck",
    "modulous",
    "myscript",
    "nevermind",
    "nocomment",
    "one_two_three",
    "painfuck",
    "pct_squared_minus_one",
    "polynomial",
    "qoibl",
    "rotfuck",
    "sbleq",
    "six_five",
    "slow_acv_mammalian",
    "sophie",
    "suffolk",
    "taglate",
    "the_temporary_stack",
    "three_d_brainfuck",
    "three_x",
    "two_d_fish",
    "unsquare",
    "wii2d",
    "ztoalc_l",
]


def main() -> None:
    """Generate a program that outputs the given text for each supported language."""
    from esolangs.registry import GENERATORS  # local import avoids a cycle

    if len(sys.argv) < 2:
        print("usage: python -m esolangs.tools.generate <text>")
        print('example: python -m esolangs.tools.generate "Hello, World!"')
        sys.exit(1)

    text = sys.argv[1]
    for name, gen in GENERATORS.items():
        print(f"--- {name} ---")
        print(gen(text))


if __name__ == "__main__":
    main()
