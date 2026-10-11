"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.false.interpreter import _LETTERS as _LETTERS
    from esolangs.languages.false.interpreter import _VARS as _VARS
    from esolangs.languages.false.interpreter import _advance as _advance
    from esolangs.languages.false.interpreter import _at as _at
    from esolangs.languages.false.interpreter import _binary as _binary
    from esolangs.languages.false.interpreter import _closers as _closers
    from esolangs.languages.false.interpreter import _Effect as _Effect
    from esolangs.languages.false.interpreter import _finalize as _finalize
    from esolangs.languages.false.interpreter import _Frame as _Frame
    from esolangs.languages.false.interpreter import _Lambda as _Lambda
    from esolangs.languages.false.interpreter import _literal as _literal
    from esolangs.languages.false.interpreter import _Loop as _Loop
    from esolangs.languages.false.interpreter import _Machine as _Machine
    from esolangs.languages.false.interpreter import _number as _number
    from esolangs.languages.false.interpreter import _pass as _pass
    from esolangs.languages.false.interpreter import _pop as _pop
    from esolangs.languages.false.interpreter import _State as _State
    from esolangs.languages.false.interpreter import _trunc_div as _trunc_div
    from esolangs.languages.false.interpreter import _Value as _Value
    from esolangs.languages.false.interpreter import _variable as _variable
    from esolangs.languages.false.interpreter import _wrap32 as _wrap32
    from esolangs.languages.false.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.false.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
