"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.slashes.interpreter import _advance as _advance
    from esolangs.languages.slashes.interpreter import _field as _field
    from esolangs.languages.slashes.interpreter import _Machine as _Machine
    from esolangs.languages.slashes.interpreter import _State as _State
    from esolangs.languages.slashes.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.slashes.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
