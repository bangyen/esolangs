"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.crement.generator import _HALT as _HALT
    from esolangs.languages.crement.generator import _HEADER_LINES as _HEADER_LINES
    from esolangs.languages.crement.generator import _LOOP as _LOOP
    from esolangs.languages.crement.generator import _NODE_LINES as _NODE_LINES
    from esolangs.languages.crement.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.crement.generator import PAIR as PAIR
    from esolangs.languages.crement.generator import _balance as _balance
    from esolangs.languages.crement.generator import (
        _crement_ordered as _crement_ordered,
    )
    from esolangs.languages.crement.generator import _crement_shared as _crement_shared
    from esolangs.languages.crement.generator import _narrow as _narrow
    from esolangs.languages.crement.generator import _rel as _rel
    from esolangs.languages.crement.generator import _same_layout as _same_layout
    from esolangs.languages.crement.generator import _short_operand as _short_operand
    from esolangs.languages.crement.generator import crement as crement
    from esolangs.languages.crement.generator import crement_setters as crement_setters

_implementation = importlib.import_module("esolangs.languages.crement.generator")
sys.modules[__name__] = _implementation
