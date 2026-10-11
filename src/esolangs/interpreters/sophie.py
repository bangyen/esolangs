"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.sophie.interpreter import _advance as _advance
    from esolangs.languages.sophie.interpreter import _brackets as _brackets
    from esolangs.languages.sophie.interpreter import _branch as _branch
    from esolangs.languages.sophie.interpreter import _Machine as _Machine
    from esolangs.languages.sophie.interpreter import _partners as _partners
    from esolangs.languages.sophie.interpreter import matches as matches
    from esolangs.languages.sophie.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.sophie.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
