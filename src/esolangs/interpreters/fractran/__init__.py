"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.fractran.interpreter import _POWER as _POWER
    from esolangs.languages.fractran.interpreter import _advance as _advance
    from esolangs.languages.fractran.interpreter import _choose as _choose
    from esolangs.languages.fractran.interpreter import _Fraction as _Fraction
    from esolangs.languages.fractran.interpreter import _Machine as _Machine
    from esolangs.languages.fractran.interpreter import _parse as _parse
    from esolangs.languages.fractran.interpreter import _product as _product
    from esolangs.languages.fractran.interpreter import _State as _State
    from esolangs.languages.fractran.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.fractran.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".index"] = importlib.import_module(
    "esolangs.languages.fractran.interpreter.index"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
