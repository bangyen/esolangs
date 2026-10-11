"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.grapheme.generator import _GRAPHEME_CONST as _GRAPHEME_CONST
    from esolangs.languages.grapheme.generator import (
        _GRAPHEME_DIGITS as _GRAPHEME_DIGITS,
    )
    from esolangs.languages.grapheme.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.grapheme.generator import (
        _grapheme_literal as _grapheme_literal,
    )
    from esolangs.languages.grapheme.generator import (
        _grapheme_push65 as _grapheme_push65,
    )
    from esolangs.languages.grapheme.generator import _grapheme_table as _grapheme_table
    from esolangs.languages.grapheme.generator import _program as _program
    from esolangs.languages.grapheme.generator import (
        balance_grapheme as balance_grapheme,
    )
    from esolangs.languages.grapheme.generator import grapheme as grapheme

_implementation = importlib.import_module("esolangs.languages.grapheme.generator")
sys.modules[__name__] = _implementation
