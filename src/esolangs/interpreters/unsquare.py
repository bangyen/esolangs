"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.unsquare.interpreter import _MAX_CHAR as _MAX_CHAR
    from esolangs.languages.unsquare.interpreter import _NEEDS as _NEEDS
    from esolangs.languages.unsquare.interpreter import _SURROGATES as _SURROGATES
    from esolangs.languages.unsquare.interpreter import _advance as _advance
    from esolangs.languages.unsquare.interpreter import _forward as _forward
    from esolangs.languages.unsquare.interpreter import _Machine as _Machine
    from esolangs.languages.unsquare.interpreter import _needs as _needs
    from esolangs.languages.unsquare.interpreter import _State as _State
    from esolangs.languages.unsquare.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.unsquare.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
