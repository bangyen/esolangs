"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.egl.interpreter import _advance as _advance
    from esolangs.languages.egl.interpreter import _Machine as _Machine
    from esolangs.languages.egl.interpreter import _Output as _Output
    from esolangs.languages.egl.interpreter import _render_grid as _render_grid
    from esolangs.languages.egl.interpreter import _State as _State
    from esolangs.languages.egl.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.egl.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
