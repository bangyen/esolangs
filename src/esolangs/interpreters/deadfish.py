"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.deadfish.interpreter import _TRAPS as _TRAPS
    from esolangs.languages.deadfish.interpreter import _advance as _advance
    from esolangs.languages.deadfish.interpreter import _Machine as _Machine
    from esolangs.languages.deadfish.interpreter import _State as _State
    from esolangs.languages.deadfish.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.deadfish.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
