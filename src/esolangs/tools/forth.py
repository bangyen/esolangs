"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.forth.generator import _FORTH_DISPATCH as _FORTH_DISPATCH
    from esolangs.languages.forth.generator import _FORTH_DROP as _FORTH_DROP
    from esolangs.languages.forth.generator import _FORTH_READ as _FORTH_READ
    from esolangs.languages.forth.generator import _FORTH_SHARE as _FORTH_SHARE
    from esolangs.languages.forth.generator import (
        _FORTH_SUBTREE_FLOOR as _FORTH_SUBTREE_FLOOR,
    )
    from esolangs.languages.forth.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.forth.generator import _forth_const as _forth_const
    from esolangs.languages.forth.generator import _forth_ordered as _forth_ordered
    from esolangs.languages.forth.generator import forth as forth

_implementation = importlib.import_module("esolangs.languages.forth.generator")
sys.modules[__name__] = _implementation
