"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.circlefuck.generator import _DIGIT_BITS as _DIGIT_BITS
    from esolangs.languages.circlefuck.generator import _READ as _READ
    from esolangs.languages.circlefuck.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.circlefuck.generator import _deleter as _deleter
    from esolangs.languages.circlefuck.generator import _program as _program
    from esolangs.languages.circlefuck.generator import (
        balance_circlefuck as balance_circlefuck,
    )
    from esolangs.languages.circlefuck.generator import circlefuck as circlefuck

_implementation = importlib.import_module("esolangs.languages.circlefuck.generator")
sys.modules[__name__] = _implementation
