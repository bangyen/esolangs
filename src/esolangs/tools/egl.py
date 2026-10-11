"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.egl.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.egl.generator import _balance as _balance
    from esolangs.languages.egl.generator import _balanced as _balanced
    from esolangs.languages.egl.generator import _program as _program
    from esolangs.languages.egl.generator import _wrap as _wrap
    from esolangs.languages.egl.generator import egl as egl

_implementation = importlib.import_module("esolangs.languages.egl.generator")
sys.modules[__name__] = _implementation
