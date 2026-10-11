"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bit_tilde.generator import (
        _BIT_TILDE_PLANTED as _BIT_TILDE_PLANTED,
    )
    from esolangs.languages.bit_tilde.generator import (
        _BIT_TILDE_WALK as _BIT_TILDE_WALK,
    )
    from esolangs.languages.bit_tilde.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.bit_tilde.generator import _program as _program
    from esolangs.languages.bit_tilde.generator import (
        balance_bit_tilde as balance_bit_tilde,
    )
    from esolangs.languages.bit_tilde.generator import bit_tilde as bit_tilde

_implementation = importlib.import_module("esolangs.languages.bit_tilde.generator")
sys.modules[__name__] = _implementation
