"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.piet_plus_plus.interpreter import _BINARY as _BINARY
    from esolangs.languages.piet_plus_plus.interpreter import _COMMANDS as _COMMANDS
    from esolangs.languages.piet_plus_plus.interpreter import _INTEGER as _INTEGER
    from esolangs.languages.piet_plus_plus.interpreter import _LEVELS as _LEVELS
    from esolangs.languages.piet_plus_plus.interpreter import BLACK as BLACK
    from esolangs.languages.piet_plus_plus.interpreter import WHITE as WHITE
    from esolangs.languages.piet_plus_plus.interpreter import Element as Element
    from esolangs.languages.piet_plus_plus.interpreter import Pixel as Pixel
    from esolangs.languages.piet_plus_plus.interpreter import Point as Point
    from esolangs.languages.piet_plus_plus.interpreter import _colour as _colour
    from esolangs.languages.piet_plus_plus.interpreter import _freeze as _freeze
    from esolangs.languages.piet_plus_plus.interpreter import _ints as _ints
    from esolangs.languages.piet_plus_plus.interpreter import _Machine as _Machine
    from esolangs.languages.piet_plus_plus.interpreter import load_source as load_source
    from esolangs.languages.piet_plus_plus.interpreter import run as run
    from esolangs.languages.piet_plus_plus.interpreter import (
        supports_scale as supports_scale,
    )

_implementation = importlib.import_module(
    "esolangs.languages.piet_plus_plus.interpreter"
)
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, loader=_implementation.load_source)
