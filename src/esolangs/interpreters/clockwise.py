"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.clockwise.interpreter import _BYTE_BITS as _BYTE_BITS
    from esolangs.languages.clockwise.interpreter import COL as COL
    from esolangs.languages.clockwise.interpreter import ROW as ROW
    from esolangs.languages.clockwise.interpreter import _advance as _advance
    from esolangs.languages.clockwise.interpreter import _Machine as _Machine
    from esolangs.languages.clockwise.interpreter import _State as _State
    from esolangs.languages.clockwise.interpreter import move as move
    from esolangs.languages.clockwise.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.clockwise.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="keep")
