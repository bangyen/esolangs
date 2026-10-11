"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.ram0.interpreter import _advance as _advance
    from esolangs.languages.ram0.interpreter import _Index as _Index
    from esolangs.languages.ram0.interpreter import _loaded as _loaded
    from esolangs.languages.ram0.interpreter import _Machine as _Machine
    from esolangs.languages.ram0.interpreter import _Ram as _Ram
    from esolangs.languages.ram0.interpreter import _State as _State
    from esolangs.languages.ram0.interpreter import _stored as _stored
    from esolangs.languages.ram0.interpreter import change as change
    from esolangs.languages.ram0.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.ram0.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
