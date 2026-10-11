"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.fractran.generator import _PARITY_BINARY as _PARITY_BINARY
    from esolangs.languages.fractran.generator import _PARITY_PAIR as _PARITY_PAIR
    from esolangs.languages.fractran.generator import _PARITY_TWO as _PARITY_TWO
    from esolangs.languages.fractran.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.fractran.generator import PAIR as PAIR
    from esolangs.languages.fractran.generator import _balance as _balance
    from esolangs.languages.fractran.generator import _Leaf as _Leaf
    from esolangs.languages.fractran.generator import _Node as _Node
    from esolangs.languages.fractran.generator import _nodes as _nodes
    from esolangs.languages.fractran.generator import _plain as _plain
    from esolangs.languages.fractran.generator import _primes as _primes
    from esolangs.languages.fractran.generator import _same_layout as _same_layout
    from esolangs.languages.fractran.generator import _start as _start
    from esolangs.languages.fractran.generator import _tree as _tree
    from esolangs.languages.fractran.generator import _unread as _unread
    from esolangs.languages.fractran.generator import _widest as _widest
    from esolangs.languages.fractran.generator import fractran as fractran
    from esolangs.languages.fractran.generator import (
        fractran_setters as fractran_setters,
    )

_implementation = importlib.import_module("esolangs.languages.fractran.generator")
sys.modules[__name__] = _implementation
