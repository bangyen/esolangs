"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.eval.interpreter import _Core as _Core
    from esolangs.languages.eval.interpreter import _Fault as _Fault
    from esolangs.languages.eval.interpreter import _Frame as _Frame
    from esolangs.languages.eval.interpreter import _iterate as _iterate
    from esolangs.languages.eval.interpreter import _Machine as _Machine
    from esolangs.languages.eval.interpreter import _popped as _popped
    from esolangs.languages.eval.interpreter import _pushed as _pushed
    from esolangs.languages.eval.interpreter import _State as _State
    from esolangs.languages.eval.interpreter import _Val as _Val
    from esolangs.languages.eval.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.eval.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
