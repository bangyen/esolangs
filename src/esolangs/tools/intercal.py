"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.intercal.generator import _ONE as _ONE
    from esolangs.languages.intercal.generator import (
        _STATEMENT_OVERHEAD as _STATEMENT_OVERHEAD,
    )
    from esolangs.languages.intercal.generator import _TOKEN as _TOKEN
    from esolangs.languages.intercal.generator import _ZERO as _ZERO
    from esolangs.languages.intercal.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.intercal.generator import PAIR as PAIR
    from esolangs.languages.intercal.generator import TEMPLATE_CHAR as TEMPLATE_CHAR
    from esolangs.languages.intercal.generator import _diagram as _diagram
    from esolangs.languages.intercal.generator import _Expr as _Expr
    from esolangs.languages.intercal.generator import (
        _intercal_shared as _intercal_shared,
    )
    from esolangs.languages.intercal.generator import (
        _intercal_tokens as _intercal_tokens,
    )
    from esolangs.languages.intercal.generator import _mux as _mux
    from esolangs.languages.intercal.generator import _negations as _negations
    from esolangs.languages.intercal.generator import _program as _program
    from esolangs.languages.intercal.generator import _same_layout as _same_layout
    from esolangs.languages.intercal.generator import _span as _span
    from esolangs.languages.intercal.generator import _variable as _variable
    from esolangs.languages.intercal.generator import _wrap_intercal as _wrap_intercal
    from esolangs.languages.intercal.generator import (
        balance_intercal as balance_intercal,
    )
    from esolangs.languages.intercal.generator import intercal as intercal

_implementation = importlib.import_module("esolangs.languages.intercal.generator")
sys.modules[__name__] = _implementation
