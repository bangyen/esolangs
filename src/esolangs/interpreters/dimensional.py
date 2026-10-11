"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.dimensional.interpreter import _AddValue as _AddValue
    from esolangs.languages.dimensional.interpreter import _advance as _advance
    from esolangs.languages.dimensional.interpreter import _Clear as _Clear
    from esolangs.languages.dimensional.interpreter import _Effect as _Effect
    from esolangs.languages.dimensional.interpreter import _FromCoord as _FromCoord
    from esolangs.languages.dimensional.interpreter import _Level as _Level
    from esolangs.languages.dimensional.interpreter import _Machine as _Machine
    from esolangs.languages.dimensional.interpreter import _matches as _matches
    from esolangs.languages.dimensional.interpreter import _Move as _Move
    from esolangs.languages.dimensional.interpreter import _number as _number
    from esolangs.languages.dimensional.interpreter import _SetValue as _SetValue
    from esolangs.languages.dimensional.interpreter import _State as _State
    from esolangs.languages.dimensional.interpreter import _Tape as _Tape
    from esolangs.languages.dimensional.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.dimensional.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
