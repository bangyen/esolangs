"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.underload.generator import _BIT_PAIR as _BIT_PAIR
    from esolangs.languages.underload.generator import _NODE as _NODE
    from esolangs.languages.underload.generator import _PREFIX as _PREFIX
    from esolangs.languages.underload.generator import _REACH as _REACH
    from esolangs.languages.underload.generator import _SHORT_PAIR as _SHORT_PAIR
    from esolangs.languages.underload.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.underload.generator import PAIR as PAIR
    from esolangs.languages.underload.generator import _balance as _balance
    from esolangs.languages.underload.generator import _reflected as _reflected
    from esolangs.languages.underload.generator import _same_layout as _same_layout
    from esolangs.languages.underload.generator import _shared as _shared
    from esolangs.languages.underload.generator import (
        _underload_layout_tokens as _underload_layout_tokens,
    )
    from esolangs.languages.underload.generator import underload as underload
    from esolangs.languages.underload.generator import (
        underload_setters as underload_setters,
    )

_implementation = importlib.import_module("esolangs.languages.underload.generator")
sys.modules[__name__] = _implementation
