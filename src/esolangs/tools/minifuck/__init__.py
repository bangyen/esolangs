"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.minifuck.generator import _INERT as _INERT
    from esolangs.languages.minifuck.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.minifuck.generator import _affine_mask as _affine_mask
    from esolangs.languages.minifuck.generator import _balance as _balance
    from esolangs.languages.minifuck.generator import _degenerate as _degenerate
    from esolangs.languages.minifuck.generator import _lookup_balance as _lookup_balance
    from esolangs.languages.minifuck.generator import _lookup_layout as _lookup_layout
    from esolangs.languages.minifuck.generator import _narrow as _narrow
    from esolangs.languages.minifuck.generator import _paired as _paired
    from esolangs.languages.minifuck.generator import _parity_columns as _parity_columns
    from esolangs.languages.minifuck.generator import _reduce as _reduce
    from esolangs.languages.minifuck.generator import _same_layout as _same_layout
    from esolangs.languages.minifuck.generator import _solve as _solve
    from esolangs.languages.minifuck.generator import _square_tail as _square_tail
    from esolangs.languages.minifuck.generator import _wrap_template as _wrap_template
    from esolangs.languages.minifuck.generator import minifuck as minifuck
    from esolangs.languages.minifuck.generator import (
        minifuck_setters as minifuck_setters,
    )

_implementation = importlib.import_module("esolangs.languages.minifuck.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".mux"] = importlib.import_module(
    "esolangs.languages.minifuck.generator.mux"
)
sys.modules[__name__ + ".pool"] = importlib.import_module(
    "esolangs.languages.minifuck.generator.pool"
)
sys.modules[__name__ + ".sim"] = importlib.import_module(
    "esolangs.languages.minifuck.generator.sim"
)
sys.modules[__name__ + ".states"] = importlib.import_module(
    "esolangs.languages.minifuck.generator.states"
)
sys.modules[__name__ + ".stored"] = importlib.import_module(
    "esolangs.languages.minifuck.generator.stored"
)
