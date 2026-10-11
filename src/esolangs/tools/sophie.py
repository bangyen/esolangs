"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.sophie.generator import (
        _SOPHIE_CHARACTERS as _SOPHIE_CHARACTERS,
    )
    from esolangs.languages.sophie.generator import _SOPHIE_RESERVED as _SOPHIE_RESERVED
    from esolangs.languages.sophie.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.sophie.generator import _payload as _payload
    from esolangs.languages.sophie.generator import _sophie_literal as _sophie_literal
    from esolangs.languages.sophie.generator import sophie as sophie
    from esolangs.languages.sophie.generator import sophie_labels as sophie_labels

_implementation = importlib.import_module("esolangs.languages.sophie.generator")
sys.modules[__name__] = _implementation
