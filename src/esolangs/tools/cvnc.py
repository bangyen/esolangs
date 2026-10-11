"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.cvnc.generator import _END_IF as _END_IF
    from esolangs.languages.cvnc.generator import _FILLER_ONSET as _FILLER_ONSET
    from esolangs.languages.cvnc.generator import _FILLER_VOWEL as _FILLER_VOWEL
    from esolangs.languages.cvnc.generator import _GOTO as _GOTO
    from esolangs.languages.cvnc.generator import _GOTO_SYLLABLE as _GOTO_SYLLABLE
    from esolangs.languages.cvnc.generator import _HALT_BASE as _HALT_BASE
    from esolangs.languages.cvnc.generator import _HALT_SQUARINGS as _HALT_SQUARINGS
    from esolangs.languages.cvnc.generator import _IF_ZERO as _IF_ZERO
    from esolangs.languages.cvnc.generator import _INCREMENT as _INCREMENT
    from esolangs.languages.cvnc.generator import _LANDING as _LANDING
    from esolangs.languages.cvnc.generator import _NASALS as _NASALS
    from esolangs.languages.cvnc.generator import _NORMALIZE as _NORMALIZE
    from esolangs.languages.cvnc.generator import _PRINT as _PRINT
    from esolangs.languages.cvnc.generator import _READ as _READ
    from esolangs.languages.cvnc.generator import _SKIP as _SKIP
    from esolangs.languages.cvnc.generator import _SQUARE as _SQUARE
    from esolangs.languages.cvnc.generator import _VOWELS as _VOWELS
    from esolangs.languages.cvnc.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.cvnc.generator import _climb as _climb
    from esolangs.languages.cvnc.generator import _consumed as _consumed
    from esolangs.languages.cvnc.generator import _direct as _direct
    from esolangs.languages.cvnc.generator import _halt as _halt
    from esolangs.languages.cvnc.generator import _leaf as _leaf
    from esolangs.languages.cvnc.generator import (
        _prologue_syllables as _prologue_syllables,
    )
    from esolangs.languages.cvnc.generator import _reach as _reach
    from esolangs.languages.cvnc.generator import _render as _render
    from esolangs.languages.cvnc.generator import _Stream as _Stream
    from esolangs.languages.cvnc.generator import _syllable_options as _syllable_options
    from esolangs.languages.cvnc.generator import _syllables as _syllables
    from esolangs.languages.cvnc.generator import _tree as _tree
    from esolangs.languages.cvnc.generator import cvnc as cvnc

_implementation = importlib.import_module("esolangs.languages.cvnc.generator")
sys.modules[__name__] = _implementation
