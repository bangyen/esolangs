"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.boolfuck.generator import _SCRATCH as _SCRATCH
    from esolangs.languages.boolfuck.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.boolfuck.generator import _boolfuck_tree as _boolfuck_tree
    from esolangs.languages.boolfuck.generator import boolfuck as boolfuck

_implementation = importlib.import_module("esolangs.languages.boolfuck.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._gates"] = importlib.import_module(
    "esolangs.languages.boolfuck.generator._gates"
)
