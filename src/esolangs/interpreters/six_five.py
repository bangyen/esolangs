"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.six_five.interpreter import _MAX_CHAR as _MAX_CHAR
    from esolangs.languages.six_five.interpreter import _advance as _advance
    from esolangs.languages.six_five.interpreter import _Machine as _Machine
    from esolangs.languages.six_five.interpreter import _marker as _marker
    from esolangs.languages.six_five.interpreter import _markers as _markers
    from esolangs.languages.six_five.interpreter import _State as _State
    from esolangs.languages.six_five.interpreter import _tokens as _tokens
    from esolangs.languages.six_five.interpreter import _written as _written
    from esolangs.languages.six_five.interpreter import num as num
    from esolangs.languages.six_five.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.six_five.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
