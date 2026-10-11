"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.decleq.interpreter import _IN as _IN
    from esolangs.languages.decleq.interpreter import _OUT as _OUT
    from esolangs.languages.decleq.interpreter import _advance as _advance
    from esolangs.languages.decleq.interpreter import _Machine as _Machine
    from esolangs.languages.decleq.interpreter import _operands as _operands
    from esolangs.languages.decleq.interpreter import _read as _read
    from esolangs.languages.decleq.interpreter import _State as _State
    from esolangs.languages.decleq.interpreter import _written as _written
    from esolangs.languages.decleq.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.decleq.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
