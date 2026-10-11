"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.forth.interpreter import _abort as _abort
    from esolangs.languages.forth.interpreter import _advance as _advance
    from esolangs.languages.forth.interpreter import _at as _at
    from esolangs.languages.forth.interpreter import _finalize as _finalize
    from esolangs.languages.forth.interpreter import _Frame as _Frame
    from esolangs.languages.forth.interpreter import _Frames as _Frames
    from esolangs.languages.forth.interpreter import _Machine as _Machine
    from esolangs.languages.forth.interpreter import _scan as _scan
    from esolangs.languages.forth.interpreter import _State as _State
    from esolangs.languages.forth.interpreter import _top as _top
    from esolangs.languages.forth.interpreter import _trunc_div as _trunc_div
    from esolangs.languages.forth.interpreter import _trunc_mod as _trunc_mod
    from esolangs.languages.forth.interpreter import _wrap32 as _wrap32
    from esolangs.languages.forth.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.forth.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
