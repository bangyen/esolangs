"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.modulous.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.modulous.generator import _balance as _balance
    from esolangs.languages.modulous.generator import modulous as modulous

_implementation = importlib.import_module("esolangs.languages.modulous.generator")
sys.modules[__name__] = _implementation
