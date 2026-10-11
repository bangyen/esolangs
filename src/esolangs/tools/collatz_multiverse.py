"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.collatz_multiverse.generator import _CM_ALIAS as _CM_ALIAS
    from esolangs.languages.collatz_multiverse.generator import _CM_CHUNK as _CM_CHUNK
    from esolangs.languages.collatz_multiverse.generator import _CM_PAD as _CM_PAD
    from esolangs.languages.collatz_multiverse.generator import (
        _CM_REGISTER as _CM_REGISTER,
    )
    from esolangs.languages.collatz_multiverse.generator import _PLAN as _PLAN
    from esolangs.languages.collatz_multiverse.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.collatz_multiverse.generator import _cm_build as _cm_build
    from esolangs.languages.collatz_multiverse.generator import (
        _cm_candidates as _cm_candidates,
    )
    from esolangs.languages.collatz_multiverse.generator import _cm_cells as _cm_cells
    from esolangs.languages.collatz_multiverse.generator import _cm_codes as _cm_codes
    from esolangs.languages.collatz_multiverse.generator import (
        _cm_constant_program as _cm_constant_program,
    )
    from esolangs.languages.collatz_multiverse.generator import (
        _cm_constants as _cm_constants,
    )
    from esolangs.languages.collatz_multiverse.generator import _cm_layout as _cm_layout
    from esolangs.languages.collatz_multiverse.generator import (
        _cm_layout_versions as _cm_layout_versions,
    )
    from esolangs.languages.collatz_multiverse.generator import (
        _cm_narrow_cells as _cm_narrow_cells,
    )
    from esolangs.languages.collatz_multiverse.generator import (
        _cm_narrow_choice as _cm_narrow_choice,
    )
    from esolangs.languages.collatz_multiverse.generator import (
        _cm_narrow_constants as _cm_narrow_constants,
    )
    from esolangs.languages.collatz_multiverse.generator import _cm_orders as _cm_orders
    from esolangs.languages.collatz_multiverse.generator import (
        _extend_plans as _extend_plans,
    )
    from esolangs.languages.collatz_multiverse.generator import _span as _span
    from esolangs.languages.collatz_multiverse.generator import (
        balance_collatz_multiverse as balance_collatz_multiverse,
    )
    from esolangs.languages.collatz_multiverse.generator import (
        collatz_multiverse as collatz_multiverse,
    )

_implementation = importlib.import_module(
    "esolangs.languages.collatz_multiverse.generator"
)
sys.modules[__name__] = _implementation
