"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.vandevelo.interpreter import _ASSIGN as _ASSIGN
    from esolangs.languages.vandevelo.interpreter import _NAME as _NAME
    from esolangs.languages.vandevelo.interpreter import _advance as _advance
    from esolangs.languages.vandevelo.interpreter import _bind as _bind
    from esolangs.languages.vandevelo.interpreter import _Expr as _Expr
    from esolangs.languages.vandevelo.interpreter import _expr as _expr
    from esolangs.languages.vandevelo.interpreter import _finish_part as _finish_part
    from esolangs.languages.vandevelo.interpreter import _Frame as _Frame
    from esolangs.languages.vandevelo.interpreter import _Machine as _Machine
    from esolangs.languages.vandevelo.interpreter import _needs_input as _needs_input
    from esolangs.languages.vandevelo.interpreter import _State as _State
    from esolangs.languages.vandevelo.interpreter import _Statement as _Statement
    from esolangs.languages.vandevelo.interpreter import _statement as _statement
    from esolangs.languages.vandevelo.interpreter import _Store as _Store
    from esolangs.languages.vandevelo.interpreter import _stored as _stored
    from esolangs.languages.vandevelo.interpreter import _Value as _Value
    from esolangs.languages.vandevelo.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.vandevelo.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
