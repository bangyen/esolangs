"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.decleq.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.decleq.generator import _decleq_build as _decleq_build
    from esolangs.languages.decleq.generator import decleq as decleq

_implementation = importlib.import_module("esolangs.languages.decleq.generator")
sys.modules[__name__] = _implementation
