"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.subleq.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.subleq.generator import _balance as _balance
    from esolangs.languages.subleq.generator import _payload as _payload
    from esolangs.languages.subleq.generator import _subleq_shared as _subleq_shared
    from esolangs.languages.subleq.generator import subleq as subleq

_implementation = importlib.import_module("esolangs.languages.subleq.generator")
sys.modules[__name__] = _implementation
