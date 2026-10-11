"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.sbleq.interpreter import _STORES as _STORES
    from esolangs.languages.sbleq.interpreter import _advance as _advance
    from esolangs.languages.sbleq.interpreter import _Machine as _Machine
    from esolangs.languages.sbleq.interpreter import _operands as _operands
    from esolangs.languages.sbleq.interpreter import _read as _read
    from esolangs.languages.sbleq.interpreter import _State as _State
    from esolangs.languages.sbleq.interpreter import _write as _write
    from esolangs.languages.sbleq.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.sbleq.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
