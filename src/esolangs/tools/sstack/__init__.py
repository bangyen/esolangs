"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.sstack.generator import _LEAF as _LEAF
    from esolangs.languages.sstack.generator import _PROLOGUE as _PROLOGUE
    from esolangs.languages.sstack.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.sstack.generator import _sstack_shared as _sstack_shared
    from esolangs.languages.sstack.generator import _sstack_tree as _sstack_tree
    from esolangs.languages.sstack.generator import sstack as sstack

_implementation = importlib.import_module("esolangs.languages.sstack.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._binary"] = importlib.import_module(
    "esolangs.languages.sstack.generator._binary"
)
sys.modules[__name__ + "._ternary"] = importlib.import_module(
    "esolangs.languages.sstack.generator._ternary"
)
