"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.circuit_diagram.generator import _COL_STEP as _COL_STEP
    from esolangs.languages.circuit_diagram.generator import _ROW_STEP as _ROW_STEP
    from esolangs.languages.circuit_diagram.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.circuit_diagram.generator import (
        _affine_circuit as _affine_circuit,
    )
    from esolangs.languages.circuit_diagram.generator import _balance as _balance
    from esolangs.languages.circuit_diagram.generator import _Builder as _Builder
    from esolangs.languages.circuit_diagram.generator import (
        _circuit_diagram_at as _circuit_diagram_at,
    )
    from esolangs.languages.circuit_diagram.generator import (
        _circuit_diagram_model as _circuit_diagram_model,
    )
    from esolangs.languages.circuit_diagram.generator import _ConstGlyph as _ConstGlyph
    from esolangs.languages.circuit_diagram.generator import _Dag as _Dag
    from esolangs.languages.circuit_diagram.generator import _dag as _dag
    from esolangs.languages.circuit_diagram.generator import (
        _essential_table as _essential_table,
    )
    from esolangs.languages.circuit_diagram.generator import _GateGlyph as _GateGlyph
    from esolangs.languages.circuit_diagram.generator import (
        _linear_shared_layout as _linear_shared_layout,
    )
    from esolangs.languages.circuit_diagram.generator import _mux as _mux
    from esolangs.languages.circuit_diagram.generator import (
        _narrowest_present as _narrowest_present,
    )
    from esolangs.languages.circuit_diagram.generator import (
        _shannon_fold as _shannon_fold,
    )
    from esolangs.languages.circuit_diagram.generator import _Value as _Value
    from esolangs.languages.circuit_diagram.generator import (
        circuit_diagram as circuit_diagram,
    )

_implementation = importlib.import_module(
    "esolangs.languages.circuit_diagram.generator"
)
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".balance"] = importlib.import_module(
    "esolangs.languages.circuit_diagram.generator.balance"
)
sys.modules[__name__ + ".hlayout"] = importlib.import_module(
    "esolangs.languages.circuit_diagram.generator.hlayout"
)
sys.modules[__name__ + ".layout"] = importlib.import_module(
    "esolangs.languages.circuit_diagram.generator.layout"
)
