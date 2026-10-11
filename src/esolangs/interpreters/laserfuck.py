"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.laserfuck.interpreter import _CELL_BITS as _CELL_BITS
    from esolangs.languages.laserfuck.interpreter import _CELL_MODULUS as _CELL_MODULUS
    from esolangs.languages.laserfuck.interpreter import _CELL_SIGN as _CELL_SIGN
    from esolangs.languages.laserfuck.interpreter import _NO_POS as _NO_POS
    from esolangs.languages.laserfuck.interpreter import _advance as _advance
    from esolangs.languages.laserfuck.interpreter import _Beams as _Beams
    from esolangs.languages.laserfuck.interpreter import _BranchState as _BranchState
    from esolangs.languages.laserfuck.interpreter import _cell_value as _cell_value
    from esolangs.languages.laserfuck.interpreter import _Machine as _Machine
    from esolangs.languages.laserfuck.interpreter import _move as _move
    from esolangs.languages.laserfuck.interpreter import _State as _State
    from esolangs.languages.laserfuck.interpreter import _strip_pos as _strip_pos
    from esolangs.languages.laserfuck.interpreter import _Tape as _Tape
    from esolangs.languages.laserfuck.interpreter import _write as _write
    from esolangs.languages.laserfuck.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.laserfuck.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="keep")
