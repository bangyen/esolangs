"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.slashes.generator import _CONSTANT as _CONSTANT
    from esolangs.languages.slashes.generator import _DECODE as _DECODE
    from esolangs.languages.slashes.generator import _IGNORE as _IGNORE
    from esolangs.languages.slashes.generator import _SWEEP as _SWEEP
    from esolangs.languages.slashes.generator import _UNARY as _UNARY
    from esolangs.languages.slashes.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.slashes.generator import (
        _is_unfilled_template as _is_unfilled_template,
    )
    from esolangs.languages.slashes.generator import slashes as slashes

_implementation = importlib.import_module("esolangs.languages.slashes.generator")
sys.modules[__name__] = _implementation
