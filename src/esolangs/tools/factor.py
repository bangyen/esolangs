"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.factor.generator import _BF_RESIDUE as _BF_RESIDUE
    from esolangs.languages.factor.generator import (
        _FACTOR_PRIME_CHUNK as _FACTOR_PRIME_CHUNK,
    )
    from esolangs.languages.factor.generator import _MODULUS as _MODULUS
    from esolangs.languages.factor.generator import _SPAN as _SPAN
    from esolangs.languages.factor.generator import _STEP as _STEP
    from esolangs.languages.factor.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.factor.generator import _encode as _encode
    from esolangs.languages.factor.generator import _factor as _factor
    from esolangs.languages.factor.generator import _primes as _primes
    from esolangs.languages.factor.generator import _program as _program
    from esolangs.languages.factor.generator import _spans as _spans
    from esolangs.languages.factor.generator import balance_factor as balance_factor
    from esolangs.languages.factor.generator import factor as factor

_implementation = importlib.import_module("esolangs.languages.factor.generator")
sys.modules[__name__] = _implementation
