"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.dimensional.generator import _COUNT_DOUBLE as _COUNT_DOUBLE
    from esolangs.languages.dimensional.generator import _COUNTER as _COUNTER
    from esolangs.languages.dimensional.generator import _DOUBLE as _DOUBLE
    from esolangs.languages.dimensional.generator import _INDEX as _INDEX
    from esolangs.languages.dimensional.generator import _PLANE as _PLANE
    from esolangs.languages.dimensional.generator import _READ as _READ
    from esolangs.languages.dimensional.generator import _SPARE as _SPARE
    from esolangs.languages.dimensional.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.dimensional.generator import _advance as _advance
    from esolangs.languages.dimensional.generator import _balance as _balance
    from esolangs.languages.dimensional.generator import _balanced as _balanced
    from esolangs.languages.dimensional.generator import _count as _count
    from esolangs.languages.dimensional.generator import (
        _dimensional_bare as _dimensional_bare,
    )
    from esolangs.languages.dimensional.generator import _paint as _paint
    from esolangs.languages.dimensional.generator import _program as _program
    from esolangs.languages.dimensional.generator import dimensional as dimensional

_implementation = importlib.import_module("esolangs.languages.dimensional.generator")
sys.modules[__name__] = _implementation
