"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.minifuck.interpreter import _QUIET as _QUIET
    from esolangs.languages.minifuck.interpreter import _WIDTH as _WIDTH
    from esolangs.languages.minifuck.interpreter import _WINDOW as _WINDOW
    from esolangs.languages.minifuck.interpreter import _advance as _advance
    from esolangs.languages.minifuck.interpreter import _Effect as _Effect
    from esolangs.languages.minifuck.interpreter import _load as _load
    from esolangs.languages.minifuck.interpreter import _Machine as _Machine
    from esolangs.languages.minifuck.interpreter import _pool as _pool
    from esolangs.languages.minifuck.interpreter import _start as _start
    from esolangs.languages.minifuck.interpreter import _State as _State
    from esolangs.languages.minifuck.interpreter import _step as _step
    from esolangs.languages.minifuck.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.minifuck.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
