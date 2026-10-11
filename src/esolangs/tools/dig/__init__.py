"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.dig.generator import _DIG_BAND as _DIG_BAND
    from esolangs.languages.dig.generator import _DIG_BRANCH as _DIG_BRANCH
    from esolangs.languages.dig.generator import _DIG_LAST as _DIG_LAST
    from esolangs.languages.dig.generator import _DIG_STRIDE as _DIG_STRIDE
    from esolangs.languages.dig.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.dig.generator import _balance as _balance
    from esolangs.languages.dig.generator import _dig_alternating as _dig_alternating
    from esolangs.languages.dig.generator import _dig_build as _dig_build
    from esolangs.languages.dig.generator import (
        _dig_center_choice as _dig_center_choice,
    )
    from esolangs.languages.dig.generator import (
        _dig_center_shared as _dig_center_shared,
    )
    from esolangs.languages.dig.generator import _dig_clear as _dig_clear
    from esolangs.languages.dig.generator import _dig_columns as _dig_columns
    from esolangs.languages.dig.generator import _dig_discards as _dig_discards
    from esolangs.languages.dig.generator import _dig_grid as _dig_grid
    from esolangs.languages.dig.generator import _dig_lane_shared as _dig_lane_shared
    from esolangs.languages.dig.generator import _dig_lay as _dig_lay
    from esolangs.languages.dig.generator import _dig_leaf as _dig_leaf
    from esolangs.languages.dig.generator import _dig_levels as _dig_levels
    from esolangs.languages.dig.generator import (
        _dig_parallel_shared as _dig_parallel_shared,
    )
    from esolangs.languages.dig.generator import _dig_quarter_turn as _dig_quarter_turn
    from esolangs.languages.dig.generator import _dig_shared_pair as _dig_shared_pair
    from esolangs.languages.dig.generator import _dig_size as _dig_size
    from esolangs.languages.dig.generator import _dig_xor_pair as _dig_xor_pair
    from esolangs.languages.dig.generator import dig as dig

_implementation = importlib.import_module("esolangs.languages.dig.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._layout"] = importlib.import_module(
    "esolangs.languages.dig.generator._layout"
)
sys.modules[__name__ + "._leaf"] = importlib.import_module(
    "esolangs.languages.dig.generator._leaf"
)
sys.modules[__name__ + "._shared"] = importlib.import_module(
    "esolangs.languages.dig.generator._shared"
)
