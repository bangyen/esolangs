"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.suffolk.generator import _COUNTS as _COUNTS
    from esolangs.languages.suffolk.generator import _DOWN as _DOWN
    from esolangs.languages.suffolk.generator import _NEGATED as _NEGATED
    from esolangs.languages.suffolk.generator import _RAW as _RAW
    from esolangs.languages.suffolk.generator import _TWO as _TWO
    from esolangs.languages.suffolk.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.suffolk.generator import _one as _one
    from esolangs.languages.suffolk.generator import _read as _read
    from esolangs.languages.suffolk.generator import _suffolk_lookup as _suffolk_lookup
    from esolangs.languages.suffolk.generator import _write as _write
    from esolangs.languages.suffolk.generator import suffolk as suffolk

_implementation = importlib.import_module("esolangs.languages.suffolk.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._shared"] = importlib.import_module(
    "esolangs.languages.suffolk.generator._shared"
)
