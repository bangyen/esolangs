"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.false.generator import _BETWEEN as _BETWEEN
    from esolangs.languages.false.generator import _CLOSE as _CLOSE
    from esolangs.languages.false.generator import _FLIPPED as _FLIPPED
    from esolangs.languages.false.generator import _OPEN as _OPEN
    from esolangs.languages.false.generator import _SAME as _SAME
    from esolangs.languages.false.generator import _SKIP as _SKIP
    from esolangs.languages.false.generator import _TEST_ONE as _TEST_ONE
    from esolangs.languages.false.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.false.generator import Key as Key
    from esolangs.languages.false.generator import _balance as _balance
    from esolangs.languages.false.generator import _shared as _shared
    from esolangs.languages.false.generator import false as false

_implementation = importlib.import_module("esolangs.languages.false.generator")
sys.modules[__name__] = _implementation
