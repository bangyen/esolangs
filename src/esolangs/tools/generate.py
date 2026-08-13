"""Text generators (re-exported from the generators package).

The generators live in ``esolangs.tools.generators``, split by language
family; this module re-exports them for compatibility and provides the
``python -m esolangs.tools.generate`` CLI.
"""

import sys

from esolangs.tools.generators.helpers import _ilog
from esolangs.tools.generators.other import (
    _123,
    basicfuck,
    between,
    bit_tilde,
    clockwise,
    container,
    dimensional,
    forth,
    home_row,
    laserfuck,
    nevermind,
    nocomment,
    painfuck,
    pct_squared_minus_one,
    sbleq,
    taglate,
    three_x,
    two_d_fish,
    unsquare,
    ztoalc,
)
from esolangs.tools.generators.register import (
    bio,
    dig,
    dotlang,
    eval,  # noqa: A004 - the language is named "Eval"
    huf,
    polynomial,
    qoibl,
    sophie,
    wii2d,
)
from esolangs.tools.generators.stack import modulous, temporary
from esolangs.tools.generators.tape import (
    ascii_art,
    bf,
    bfstack,
    brainif,
    circlefuck,
    excon,
    factor,
    mammalian,
    minifuck,
    six_five,
    suffolk,
)

__all__ = [
    "_123",
    "_ilog",
    "ascii_art",
    "basicfuck",
    "between",
    "bf",
    "bfstack",
    "bio",
    "bit_tilde",
    "brainif",
    "circlefuck",
    "clockwise",
    "container",
    "dig",
    "dimensional",
    "dotlang",
    "eval",
    "excon",
    "factor",
    "forth",
    "home_row",
    "huf",
    "laserfuck",
    "mammalian",
    "minifuck",
    "modulous",
    "nevermind",
    "nocomment",
    "painfuck",
    "pct_squared_minus_one",
    "polynomial",
    "qoibl",
    "sbleq",
    "six_five",
    "sophie",
    "suffolk",
    "taglate",
    "temporary",
    "three_x",
    "two_d_fish",
    "unsquare",
    "wii2d",
    "ztoalc",
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
