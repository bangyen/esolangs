"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.alight.generator import (
        _ALIGHT_EAST_TURN as _ALIGHT_EAST_TURN,
    )
    from esolangs.languages.alight.generator import _ALIGHT_OVERHEAD as _ALIGHT_OVERHEAD
    from esolangs.languages.alight.generator import (
        _ALIGHT_WEST_TURN as _ALIGHT_WEST_TURN,
    )
    from esolangs.languages.alight.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.alight.generator import _alight_chunk as _alight_chunk
    from esolangs.languages.alight.generator import (
        _alight_flat_compact as _alight_flat_compact,
    )
    from esolangs.languages.alight.generator import _alight_folded as _alight_folded
    from esolangs.languages.alight.generator import _alight_units as _alight_units
    from esolangs.languages.alight.generator import _balance as _balance
    from esolangs.languages.alight.generator import _constant_units as _constant_units
    from esolangs.languages.alight.generator import _dialect as _dialect
    from esolangs.languages.alight.generator import _dimensions as _dimensions
    from esolangs.languages.alight.generator import _fit as _fit
    from esolangs.languages.alight.generator import _flatten as _flatten
    from esolangs.languages.alight.generator import _half_before as _half_before
    from esolangs.languages.alight.generator import _postfix_units as _postfix_units
    from esolangs.languages.alight.generator import _postfix_width as _postfix_width
    from esolangs.languages.alight.generator import _program as _program
    from esolangs.languages.alight.generator import _smallest as _smallest
    from esolangs.languages.alight.generator import alight as alight

_implementation = importlib.import_module("esolangs.languages.alight.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".balance"] = importlib.import_module(
    "esolangs.languages.alight.generator.balance"
)
