"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bit_tilde.interpreter import _advance as _advance
    from esolangs.languages.bit_tilde.interpreter import _grown as _grown
    from esolangs.languages.bit_tilde.interpreter import _Machine as _Machine
    from esolangs.languages.bit_tilde.interpreter import _match as _match
    from esolangs.languages.bit_tilde.interpreter import _State as _State
    from esolangs.languages.bit_tilde.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.bit_tilde.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
