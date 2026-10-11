"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.fargo.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.fargo.generator import _arm_expression as _arm_expression
    from esolangs.languages.fargo.generator import _balance as _balance
    from esolangs.languages.fargo.generator import (
        _definition_program as _definition_program,
    )
    from esolangs.languages.fargo.generator import _expression as _expression
    from esolangs.languages.fargo.generator import _word_width as _word_width
    from esolangs.languages.fargo.generator import anf_coefficients as anf_coefficients
    from esolangs.languages.fargo.generator import fargo as fargo

_implementation = importlib.import_module("esolangs.languages.fargo.generator")
sys.modules[__name__] = _implementation
