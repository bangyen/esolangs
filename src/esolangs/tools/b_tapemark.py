"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.b_tapemark.generator import _NARROW_STAGE as _NARROW_STAGE
    from esolangs.languages.b_tapemark.generator import _RUN_COLUMN as _RUN_COLUMN
    from esolangs.languages.b_tapemark.generator import _STAGE as _STAGE
    from esolangs.languages.b_tapemark.generator import _STAGE_ROWS as _STAGE_ROWS
    from esolangs.languages.b_tapemark.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.b_tapemark.generator import (
        _b_tapemark_narrow as _b_tapemark_narrow,
    )
    from esolangs.languages.b_tapemark.generator import (
        _b_tapemark_program as _b_tapemark_program,
    )
    from esolangs.languages.b_tapemark.generator import _balance as _balance
    from esolangs.languages.b_tapemark.generator import _Builder as _Builder
    from esolangs.languages.b_tapemark.generator import b_tapemark as b_tapemark

_implementation = importlib.import_module("esolangs.languages.b_tapemark.generator")
sys.modules[__name__] = _implementation
