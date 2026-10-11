"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.streetcode.interpreter import _Edges as _Edges
    from esolangs.languages.streetcode.interpreter import _Machine as _Machine
    from esolangs.languages.streetcode.interpreter import _State as _State
    from esolangs.languages.streetcode.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.streetcode.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".geometry"] = importlib.import_module(
    "esolangs.languages.streetcode.interpreter.geometry"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="strip")
