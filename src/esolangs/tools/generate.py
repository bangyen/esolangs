"""Text generators (re-exported from the generators package).

The generators live in ``esolangs.tools.generators``, split by language
family; this module re-exports them for compatibility and provides the
``python -m esolangs.tools.generate`` CLI.
"""

import sys

from esolangs.tools.generators.helpers import _ilog
from esolangs.tools.generators.other import (
    _123,
    clockwise,
    container,
    forth,
    home_row,
    laserfuck,
    magnitude,
    nevermind,
    nocomment,
    painfuck,
    taglate,
    unsquare,
    ztoalc,
)
from esolangs.tools.generators.register import (
    bio,
    dig,
    dotlang,
    eval,
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
    mammalian,
    minifuck,
    six_five,
    suffolk,
)

__all__ = [
    "_123",
    "_ilog",
    "ascii_art",
    "bf",
    "bfstack",
    "bio",
    "brainif",
    "circlefuck",
    "clockwise",
    "container",
    "dig",
    "dotlang",
    "eval",
    "excon",
    "forth",
    "home_row",
    "huf",
    "laserfuck",
    "magnitude",
    "mammalian",
    "minifuck",
    "modulous",
    "nevermind",
    "nocomment",
    "painfuck",
    "polynomial",
    "qoibl",
    "six_five",
    "sophie",
    "suffolk",
    "taglate",
    "temporary",
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
