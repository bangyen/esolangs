"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.hq9.interpreter import _SONG as _SONG
    from esolangs.languages.hq9.interpreter import _advance as _advance
    from esolangs.languages.hq9.interpreter import _bottles as _bottles
    from esolangs.languages.hq9.interpreter import _Machine as _Machine
    from esolangs.languages.hq9.interpreter import _State as _State
    from esolangs.languages.hq9.interpreter import _verse as _verse
    from esolangs.languages.hq9.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.hq9.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
