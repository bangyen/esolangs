"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.thisthat.interpreter import (
        _ARROW_DIRECTION as _ARROW_DIRECTION,
    )
    from esolangs.languages.thisthat.interpreter import _ARROWS as _ARROWS
    from esolangs.languages.thisthat.interpreter import _BLACK_SIDE as _BLACK_SIDE
    from esolangs.languages.thisthat.interpreter import _DIRECTION as _DIRECTION
    from esolangs.languages.thisthat.interpreter import _DOUBLE as _DOUBLE
    from esolangs.languages.thisthat.interpreter import _NODES as _NODES
    from esolangs.languages.thisthat.interpreter import _OPPOSITE as _OPPOSITE
    from esolangs.languages.thisthat.interpreter import _PORTS as _PORTS
    from esolangs.languages.thisthat.interpreter import _PRIORITY as _PRIORITY
    from esolangs.languages.thisthat.interpreter import _SINGLE as _SINGLE
    from esolangs.languages.thisthat.interpreter import _STEP as _STEP
    from esolangs.languages.thisthat.interpreter import _WHITE_SIDE as _WHITE_SIDE
    from esolangs.languages.thisthat.interpreter import _BranchDraw as _BranchDraw
    from esolangs.languages.thisthat.interpreter import _Channel as _Channel
    from esolangs.languages.thisthat.interpreter import _Machine as _Machine
    from esolangs.languages.thisthat.interpreter import _Point as _Point
    from esolangs.languages.thisthat.interpreter import _Pointer as _Pointer
    from esolangs.languages.thisthat.interpreter import _State as _State
    from esolangs.languages.thisthat.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.thisthat.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="keep")
