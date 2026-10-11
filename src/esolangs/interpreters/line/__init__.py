"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.line.interpreter import _compiled as _compiled
    from esolangs.languages.line.interpreter import _grey_rows as _grey_rows
    from esolangs.languages.line.interpreter import _Machine as _Machine
    from esolangs.languages.line.interpreter import load_source as load_source
    from esolangs.languages.line.interpreter import run as run
    from esolangs.languages.line.interpreter import supports_scale as supports_scale

_implementation = importlib.import_module("esolangs.languages.line.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".extract"] = importlib.import_module(
    "esolangs.languages.line.interpreter.extract"
)
sys.modules[__name__ + ".lattice"] = importlib.import_module(
    "esolangs.languages.line.interpreter.lattice"
)
sys.modules[__name__ + ".mask"] = importlib.import_module(
    "esolangs.languages.line.interpreter.mask"
)
sys.modules[__name__ + ".simulate"] = importlib.import_module(
    "esolangs.languages.line.interpreter.simulate"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, loader=_implementation.load_source)
