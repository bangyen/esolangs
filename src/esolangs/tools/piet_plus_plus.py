"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.piet_plus_plus.generator import _DELTAS as _DELTAS
    from esolangs.languages.piet_plus_plus.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.piet_plus_plus.generator import _generate as _generate
    from esolangs.languages.piet_plus_plus.generator import _next_colour as _next_colour
    from esolangs.languages.piet_plus_plus.generator import (
        piet_plus_plus as piet_plus_plus,
    )

_implementation = importlib.import_module("esolangs.languages.piet_plus_plus.generator")
sys.modules[__name__] = _implementation
