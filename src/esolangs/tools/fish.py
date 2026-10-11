"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.fish.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.fish.generator import balance_fish as balance_fish
    from esolangs.languages.fish.generator import fish as fish

_implementation = importlib.import_module("esolangs.languages.fish.generator")
sys.modules[__name__] = _implementation
