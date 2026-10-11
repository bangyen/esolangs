"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.smu.generator import _LETTERS as _LETTERS
    from esolangs.languages.smu.generator import _MACROS as _MACROS
    from esolangs.languages.smu.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.smu.generator import _name as _name
    from esolangs.languages.smu.generator import smu as smu

_implementation = importlib.import_module("esolangs.languages.smu.generator")
sys.modules[__name__] = _implementation
