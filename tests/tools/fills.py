"""The parameterized substitutions by name, for suites that fill a template.

The package keeps one ``setters`` function per embedding language and
derives each example's ``fill`` from it (``_fill_from``); the suites that
exercise a single language's substitution reach it here by name rather
than through the example table.
"""

from esolangs.tools.examples import (
    _body_pct_squared_minus_one,
    _fill_from,
    _setters_back,
    _setters_bfpda,
    _setters_bio,
    _setters_bitdeque,
    _setters_eval,
    _setters_home_row,
    _setters_minifuck,
    _setters_minsky_swap,
    _setters_nocomment,
    _setters_pct_squared_minus_one,
    _setters_ram0,
    _setters_wii2d,
)

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

_fill_bio = _fill_from(_setters_bio)
_fill_nocomment = _fill_from(_setters_nocomment)
_fill_bitdeque = _fill_from(_setters_bitdeque)
_fill_bfpda = _fill_from(_setters_bfpda)
_fill_back = _fill_from(_setters_back)
_fill_minsky_swap = _fill_from(_setters_minsky_swap)
_fill_ram0 = _fill_from(_setters_ram0)
_fill_home_row = _fill_from(_setters_home_row)
_fill_eval = _fill_from(_setters_eval)
_fill_wii2d = _fill_from(_setters_wii2d)
_fill_minifuck = _fill_from(_setters_minifuck)
_fill_pct_squared_minus_one = _fill_from(
    _setters_pct_squared_minus_one, _body_pct_squared_minus_one
)
