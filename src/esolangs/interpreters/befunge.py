"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.befunge.interpreter import _DIRECTIONS as _DIRECTIONS
    from esolangs.languages.befunge.interpreter import _HEIGHT as _HEIGHT
    from esolangs.languages.befunge.interpreter import _LONG_BITS as _LONG_BITS
    from esolangs.languages.befunge.interpreter import _MAX_VALUE as _MAX_VALUE
    from esolangs.languages.befunge.interpreter import _MIN_VALUE as _MIN_VALUE
    from esolangs.languages.befunge.interpreter import _WIDTH as _WIDTH
    from esolangs.languages.befunge.interpreter import _advance as _advance
    from esolangs.languages.befunge.interpreter import _Cursor as _Cursor
    from esolangs.languages.befunge.interpreter import _Effect as _Effect
    from esolangs.languages.befunge.interpreter import _Grid as _Grid
    from esolangs.languages.befunge.interpreter import _Machine as _Machine
    from esolangs.languages.befunge.interpreter import _pop as _pop
    from esolangs.languages.befunge.interpreter import _push as _push
    from esolangs.languages.befunge.interpreter import _Stack as _Stack
    from esolangs.languages.befunge.interpreter import _State as _State
    from esolangs.languages.befunge.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.befunge.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="strip")
