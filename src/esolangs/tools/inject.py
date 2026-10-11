"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.inject.generator import _ALPHABET as _ALPHABET
    from esolangs.languages.inject.generator import _CONSTANTS as _CONSTANTS
    from esolangs.languages.inject.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.inject.generator import _balance as _balance
    from esolangs.languages.inject.generator import _halve as _halve
    from esolangs.languages.inject.generator import _inject_banded as _inject_banded
    from esolangs.languages.inject.generator import _inject_halving as _inject_halving
    from esolangs.languages.inject.generator import _inject_ordered as _inject_ordered
    from esolangs.languages.inject.generator import _leaf as _leaf
    from esolangs.languages.inject.generator import _Names as _Names
    from esolangs.languages.inject.generator import _preamble as _preamble
    from esolangs.languages.inject.generator import _tree as _tree
    from esolangs.languages.inject.generator import _widest as _widest
    from esolangs.languages.inject.generator import _word as _word
    from esolangs.languages.inject.generator import inject as inject

_implementation = importlib.import_module("esolangs.languages.inject.generator")
sys.modules[__name__] = _implementation
