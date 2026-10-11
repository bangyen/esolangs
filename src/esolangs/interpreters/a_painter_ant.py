"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.a_painter_ant.interpreter import _HEADING as _HEADING
    from esolangs.languages.a_painter_ant.interpreter import (
        _INSTRUCTIONS as _INSTRUCTIONS,
    )
    from esolangs.languages.a_painter_ant.interpreter import _MOVE as _MOVE
    from esolangs.languages.a_painter_ant.interpreter import _advance as _advance
    from esolangs.languages.a_painter_ant.interpreter import _colour as _colour
    from esolangs.languages.a_painter_ant.interpreter import _Grid as _Grid
    from esolangs.languages.a_painter_ant.interpreter import _Heading as _Heading
    from esolangs.languages.a_painter_ant.interpreter import _Machine as _Machine
    from esolangs.languages.a_painter_ant.interpreter import _Move as _Move
    from esolangs.languages.a_painter_ant.interpreter import _State as _State
    from esolangs.languages.a_painter_ant.interpreter import run as run

_implementation = importlib.import_module(
    "esolangs.languages.a_painter_ant.interpreter"
)
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
