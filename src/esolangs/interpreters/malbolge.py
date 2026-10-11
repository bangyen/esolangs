"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.malbolge.interpreter import _CRAZY as _CRAZY
    from esolangs.languages.malbolge.interpreter import _EOF as _EOF
    from esolangs.languages.malbolge.interpreter import _ROTATE as _ROTATE
    from esolangs.languages.malbolge.interpreter import _WORDS as _WORDS
    from esolangs.languages.malbolge.interpreter import _XLAT1 as _XLAT1
    from esolangs.languages.malbolge.interpreter import _XLAT2 as _XLAT2
    from esolangs.languages.malbolge.interpreter import _advance as _advance
    from esolangs.languages.malbolge.interpreter import _crazy as _crazy
    from esolangs.languages.malbolge.interpreter import _Effect as _Effect
    from esolangs.languages.malbolge.interpreter import (
        _initial_memory as _initial_memory,
    )
    from esolangs.languages.malbolge.interpreter import _load as _load
    from esolangs.languages.malbolge.interpreter import _Machine as _Machine
    from esolangs.languages.malbolge.interpreter import _op as _op
    from esolangs.languages.malbolge.interpreter import _State as _State
    from esolangs.languages.malbolge.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.malbolge.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
