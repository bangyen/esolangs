"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.polynomial.generator import (
        _POLYNOMIAL_MAX_ESTIMATED_CHARS as _POLYNOMIAL_MAX_ESTIMATED_CHARS,
    )
    from esolangs.languages.polynomial.generator import (
        _POLYNOMIAL_MAX_INSTRS as _POLYNOMIAL_MAX_INSTRS,
    )
    from esolangs.languages.polynomial.generator import (
        _POLYNOMIAL_SCREEN_SLACK as _POLYNOMIAL_SCREEN_SLACK,
    )
    from esolangs.languages.polynomial.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.polynomial.generator import (
        _polynomial_assemble as _polynomial_assemble,
    )
    from esolangs.languages.polynomial.generator import (
        _polynomial_dag as _polynomial_dag,
    )
    from esolangs.languages.polynomial.generator import (
        _polynomial_factors as _polynomial_factors,
    )
    from esolangs.languages.polynomial.generator import (
        _polynomial_hybrid as _polynomial_hybrid,
    )
    from esolangs.languages.polynomial.generator import (
        _polynomial_hybrid_cost as _polynomial_hybrid_cost,
    )
    from esolangs.languages.polynomial.generator import (
        _polynomial_labels as _polynomial_labels,
    )
    from esolangs.languages.polynomial.generator import (
        _polynomial_states as _polynomial_states,
    )
    from esolangs.languages.polynomial.generator import (
        balance_polynomial as balance_polynomial,
    )
    from esolangs.languages.polynomial.generator import polynomial as polynomial

_implementation = importlib.import_module("esolangs.languages.polynomial.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".algebra"] = importlib.import_module(
    "esolangs.languages.polynomial.generator.algebra"
)
sys.modules[__name__ + ".resources"] = importlib.import_module(
    "esolangs.languages.polynomial.generator.resources"
)
