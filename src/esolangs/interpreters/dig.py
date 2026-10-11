"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.dig.interpreter import _CONTROL as _CONTROL
    from esolangs.languages.dig.interpreter import _DIRECT as _DIRECT
    from esolangs.languages.dig.interpreter import _advance as _advance
    from esolangs.languages.dig.interpreter import _Cell as _Cell
    from esolangs.languages.dig.interpreter import _Grid as _Grid
    from esolangs.languages.dig.interpreter import _Machine as _Machine
    from esolangs.languages.dig.interpreter import _padded_grid as _padded_grid
    from esolangs.languages.dig.interpreter import _State as _State
    from esolangs.languages.dig.interpreter import _value as _value
    from esolangs.languages.dig.interpreter import _write as _write
    from esolangs.languages.dig.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.dig.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="keep")
