"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.fish.interpreter import _DIRECTIONS as _DIRECTIONS
    from esolangs.languages.fish.interpreter import _NOP as _NOP
    from esolangs.languages.fish.interpreter import Number as Number
    from esolangs.languages.fish.interpreter import _calculate as _calculate
    from esolangs.languages.fish.interpreter import _character as _character
    from esolangs.languages.fish.interpreter import _integer as _integer
    from esolangs.languages.fish.interpreter import _Machine as _Machine
    from esolangs.languages.fish.interpreter import _State as _State
    from esolangs.languages.fish.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.fish.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
