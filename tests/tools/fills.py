"""The parameterized substitutions by name, for suites that fill a template.

The package keeps one ``PAIR`` per uniform embedding language (or one
``setters`` function, for the two that read the pairs off the template)
and derives each example's ``fill`` from it (``_fill_from``); the suites
that exercise a single language's substitution reach it here by name
rather than through the example table.
"""

from esolangs.tools.back import PAIR as BACK_PAIR
from esolangs.tools.eval_lang import PAIR as EVAL_PAIR
from esolangs.tools.examples import _fill_from, uniform
from esolangs.tools.minifuck_sim import PAIR as MINIFUCK_PAIR
from esolangs.tools.nocomment import PAIR as NOCOMMENT_PAIR
from esolangs.tools.parameterized import (
    BFPDA_PAIR,
    BIO_PAIR,
    BITDEQUE_PAIR,
    HOME_ROW_PAIR,
    MINSKY_SWAP_PAIR,
)
from esolangs.tools.pct_squared_minus_one import body as pct_body
from esolangs.tools.pct_squared_minus_one import setters as pct_setters
from esolangs.tools.ram0 import PAIR as RAM0_PAIR
from esolangs.tools.wii2d import PAIR as WII2D_PAIR

__all__ = [
    "_fill_back",
    "_fill_bfpda",
    "_fill_bio",
    "_fill_bitdeque",
    "_fill_eval",
    "_fill_home_row",
    "_fill_minifuck",
    "_fill_minsky_swap",
    "_fill_nocomment",
    "_fill_pct_squared_minus_one",
    "_fill_ram0",
    "_fill_wii2d",
]

_fill_bio = _fill_from(uniform(BIO_PAIR))
_fill_nocomment = _fill_from(uniform(NOCOMMENT_PAIR))
_fill_bitdeque = _fill_from(uniform(BITDEQUE_PAIR))
_fill_bfpda = _fill_from(uniform(BFPDA_PAIR))
_fill_back = _fill_from(uniform(BACK_PAIR))
_fill_minsky_swap = _fill_from(uniform(MINSKY_SWAP_PAIR))
_fill_ram0 = _fill_from(uniform(RAM0_PAIR))
_fill_home_row = _fill_from(uniform(HOME_ROW_PAIR))
_fill_eval = _fill_from(uniform(EVAL_PAIR))
_fill_wii2d = _fill_from(uniform(WII2D_PAIR))
_fill_minifuck = _fill_from(uniform(MINIFUCK_PAIR))
_fill_pct_squared_minus_one = _fill_from(pct_setters, pct_body)
