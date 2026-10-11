"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.befunge.generator import _ASCII_ZERO as _ASCII_ZERO
    from esolangs.languages.befunge.generator import _BOUND_NARROW as _BOUND_NARROW
    from esolangs.languages.befunge.generator import _BOUND_PACKED as _BOUND_PACKED
    from esolangs.languages.befunge.generator import _BOUND_WIDE as _BOUND_WIDE
    from esolangs.languages.befunge.generator import _END as _END
    from esolangs.languages.befunge.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.befunge.generator import MAX_INPUTS as MAX_INPUTS
    from esolangs.languages.befunge.generator import _check_cap as _check_cap
    from esolangs.languages.befunge.generator import _fold_header as _fold_header
    from esolangs.languages.befunge.generator import _header as _header
    from esolangs.languages.befunge.generator import _literal as _literal
    from esolangs.languages.befunge.generator import _packed_befunge as _packed_befunge
    from esolangs.languages.befunge.generator import balance_befunge as balance_befunge
    from esolangs.languages.befunge.generator import befunge as befunge

_implementation = importlib.import_module("esolangs.languages.befunge.generator")
sys.modules[__name__] = _implementation
