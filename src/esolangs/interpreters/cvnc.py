"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.cvnc.interpreter import _ADDITIVE as _ADDITIVE
    from esolangs.languages.cvnc.interpreter import _APPROXIMANTS as _APPROXIMANTS
    from esolangs.languages.cvnc.interpreter import _CLEAR_FUNCTION as _CLEAR_FUNCTION
    from esolangs.languages.cvnc.interpreter import _CONSONANTS as _CONSONANTS
    from esolangs.languages.cvnc.interpreter import _DECREMENT as _DECREMENT
    from esolangs.languages.cvnc.interpreter import _FRICATIVES as _FRICATIVES
    from esolangs.languages.cvnc.interpreter import (
        _FUNCTION_SYMBOLS as _FUNCTION_SYMBOLS,
    )
    from esolangs.languages.cvnc.interpreter import _GOTO as _GOTO
    from esolangs.languages.cvnc.interpreter import _GOTO_LINE as _GOTO_LINE
    from esolangs.languages.cvnc.interpreter import _INCREMENT as _INCREMENT
    from esolangs.languages.cvnc.interpreter import _LOOP_END as _LOOP_END
    from esolangs.languages.cvnc.interpreter import _MULTIPLICATIVE as _MULTIPLICATIVE
    from esolangs.languages.cvnc.interpreter import _NASALS as _NASALS
    from esolangs.languages.cvnc.interpreter import _PLOSIVES as _PLOSIVES
    from esolangs.languages.cvnc.interpreter import _POP_FRONT as _POP_FRONT
    from esolangs.languages.cvnc.interpreter import (
        _POP_FRONT_APPEND as _POP_FRONT_APPEND,
    )
    from esolangs.languages.cvnc.interpreter import _PRINT_CHAR as _PRINT_CHAR
    from esolangs.languages.cvnc.interpreter import _PRINT_NUM as _PRINT_NUM
    from esolangs.languages.cvnc.interpreter import _PUSH_BACK as _PUSH_BACK
    from esolangs.languages.cvnc.interpreter import _PUSH_FRONT as _PUSH_FRONT
    from esolangs.languages.cvnc.interpreter import _READ_CHAR as _READ_CHAR
    from esolangs.languages.cvnc.interpreter import _READ_NUM as _READ_NUM
    from esolangs.languages.cvnc.interpreter import _RING as _RING
    from esolangs.languages.cvnc.interpreter import _SCRIPT_G as _SCRIPT_G
    from esolangs.languages.cvnc.interpreter import _SQRT as _SQRT
    from esolangs.languages.cvnc.interpreter import _SQUARE as _SQUARE
    from esolangs.languages.cvnc.interpreter import _VOWELS as _VOWELS
    from esolangs.languages.cvnc.interpreter import _WHILE_NONZERO as _WHILE_NONZERO
    from esolangs.languages.cvnc.interpreter import _WHILE_ZERO as _WHILE_ZERO
    from esolangs.languages.cvnc.interpreter import _advance as _advance
    from esolangs.languages.cvnc.interpreter import _applied as _applied
    from esolangs.languages.cvnc.interpreter import _approximant as _approximant
    from esolangs.languages.cvnc.interpreter import _as_int as _as_int
    from esolangs.languages.cvnc.interpreter import _fricative as _fricative
    from esolangs.languages.cvnc.interpreter import (
        _InvalidFunctionError as _InvalidFunctionError,
    )
    from esolangs.languages.cvnc.interpreter import _Machine as _Machine
    from esolangs.languages.cvnc.interpreter import _match_loops as _match_loops
    from esolangs.languages.cvnc.interpreter import _nasal as _nasal
    from esolangs.languages.cvnc.interpreter import _Parser as _Parser
    from esolangs.languages.cvnc.interpreter import _plosive as _plosive
    from esolangs.languages.cvnc.interpreter import _popped as _popped
    from esolangs.languages.cvnc.interpreter import _State as _State
    from esolangs.languages.cvnc.interpreter import _syllabify as _syllabify
    from esolangs.languages.cvnc.interpreter import _tokenize as _tokenize
    from esolangs.languages.cvnc.interpreter import _vowel as _vowel
    from esolangs.languages.cvnc.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.cvnc.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
