"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.addsubjump.generator import _ADD as _ADD
    from esolangs.languages.addsubjump.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.addsubjump.generator import (
        _addsubjump_candidate as _addsubjump_candidate,
    )
    from esolangs.languages.addsubjump.generator import (
        _addsubjump_ordered as _addsubjump_ordered,
    )
    from esolangs.languages.addsubjump.generator import (
        _addsubjump_packed as _addsubjump_packed,
    )
    from esolangs.languages.addsubjump.generator import _packed_build as _packed_build
    from esolangs.languages.addsubjump.generator import addsubjump as addsubjump
    from esolangs.languages.addsubjump.generator import (
        balance_addsubjump as balance_addsubjump,
    )

_implementation = importlib.import_module("esolangs.languages.addsubjump.generator")
sys.modules[__name__] = _implementation
