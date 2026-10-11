"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.b_tapemark.interpreter import _COMMANDS as _COMMANDS
    from esolangs.languages.b_tapemark.interpreter import _DIRECTIONS as _DIRECTIONS
    from esolangs.languages.b_tapemark.interpreter import _MIRRORS as _MIRRORS
    from esolangs.languages.b_tapemark.interpreter import _STARTS as _STARTS
    from esolangs.languages.b_tapemark.interpreter import _advance as _advance
    from esolangs.languages.b_tapemark.interpreter import _Grid as _Grid
    from esolangs.languages.b_tapemark.interpreter import _Grids as _Grids
    from esolangs.languages.b_tapemark.interpreter import _load as _load
    from esolangs.languages.b_tapemark.interpreter import _Machine as _Machine
    from esolangs.languages.b_tapemark.interpreter import _move as _move
    from esolangs.languages.b_tapemark.interpreter import _Point as _Point
    from esolangs.languages.b_tapemark.interpreter import _read as _read
    from esolangs.languages.b_tapemark.interpreter import _State as _State
    from esolangs.languages.b_tapemark.interpreter import _write as _write
    from esolangs.languages.b_tapemark.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.b_tapemark.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
