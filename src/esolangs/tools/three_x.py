"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.three_x.generator import _COMPLEMENT as _COMPLEMENT
    from esolangs.languages.three_x.generator import _NEG_ONE as _NEG_ONE
    from esolangs.languages.three_x.generator import _ONE as _ONE
    from esolangs.languages.three_x.generator import _RESULT as _RESULT
    from esolangs.languages.three_x.generator import _SCALE as _SCALE
    from esolangs.languages.three_x.generator import _SHARE_MIN as _SHARE_MIN
    from esolangs.languages.three_x.generator import _SWAP as _SWAP
    from esolangs.languages.three_x.generator import _ZERO as _ZERO
    from esolangs.languages.three_x.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.three_x.generator import _constants as _constants
    from esolangs.languages.three_x.generator import _level as _level
    from esolangs.languages.three_x.generator import _three_x_build as _three_x_build
    from esolangs.languages.three_x.generator import _three_x_emit as _three_x_emit
    from esolangs.languages.three_x.generator import (
        _three_x_ordered as _three_x_ordered,
    )
    from esolangs.languages.three_x.generator import three_x as three_x

_implementation = importlib.import_module("esolangs.languages.three_x.generator")
sys.modules[__name__] = _implementation
