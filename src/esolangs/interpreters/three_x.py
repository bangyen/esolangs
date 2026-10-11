"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.three_x.interpreter import _NEEDS as _NEEDS
    from esolangs.languages.three_x.interpreter import _RATIONAL as _RATIONAL
    from esolangs.languages.three_x.interpreter import _UNSET as _UNSET
    from esolangs.languages.three_x.interpreter import _advance as _advance
    from esolangs.languages.three_x.interpreter import _forward as _forward
    from esolangs.languages.three_x.interpreter import _loaded as _loaded
    from esolangs.languages.three_x.interpreter import _Machine as _Machine
    from esolangs.languages.three_x.interpreter import _needs as _needs
    from esolangs.languages.three_x.interpreter import _State as _State
    from esolangs.languages.three_x.interpreter import _stored as _stored
    from esolangs.languages.three_x.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.three_x.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
