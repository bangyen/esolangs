"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.unary.interpreter import _Machine as _Machine
    from esolangs.languages.unary.interpreter import _State as _State
    from esolangs.languages.unary.interpreter import _UnaryBFMachine as _UnaryBFMachine
    from esolangs.languages.unary.interpreter import decode as decode
    from esolangs.languages.unary.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.unary.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
