"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.circlefuck.interpreter import _advance as _advance
    from esolangs.languages.circlefuck.interpreter import _Edit as _Edit
    from esolangs.languages.circlefuck.interpreter import _Machine as _Machine
    from esolangs.languages.circlefuck.interpreter import _Move as _Move
    from esolangs.languages.circlefuck.interpreter import _parsed as _parsed
    from esolangs.languages.circlefuck.interpreter import _State as _State
    from esolangs.languages.circlefuck.interpreter import find as find
    from esolangs.languages.circlefuck.interpreter import parse as parse
    from esolangs.languages.circlefuck.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.circlefuck.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
