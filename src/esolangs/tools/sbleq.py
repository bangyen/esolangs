"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.sbleq.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.sbleq.generator import _balance as _balance
    from esolangs.languages.sbleq.generator import _sbleq_shared as _sbleq_shared
    from esolangs.languages.sbleq.generator import sbleq as sbleq

_implementation = importlib.import_module("esolangs.languages.sbleq.generator")
sys.modules[__name__] = _implementation
