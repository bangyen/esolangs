"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.painfuck.interpreter import _CYCLES as _CYCLES
    from esolangs.languages.painfuck.interpreter import _IDEMPOTENT as _IDEMPOTENT
    from esolangs.languages.painfuck.interpreter import _NUL as _NUL
    from esolangs.languages.painfuck.interpreter import _advance as _advance
    from esolangs.languages.painfuck.interpreter import _Coins as _Coins
    from esolangs.languages.painfuck.interpreter import _Effect as _Effect
    from esolangs.languages.painfuck.interpreter import _grow as _grow
    from esolangs.languages.painfuck.interpreter import _half as _half
    from esolangs.languages.painfuck.interpreter import _Halted as _Halted
    from esolangs.languages.painfuck.interpreter import _Machine as _Machine
    from esolangs.languages.painfuck.interpreter import _NeedCoin as _NeedCoin
    from esolangs.languages.painfuck.interpreter import _NeedRead as _NeedRead
    from esolangs.languages.painfuck.interpreter import _Print as _Print
    from esolangs.languages.painfuck.interpreter import _Reader as _Reader
    from esolangs.languages.painfuck.interpreter import _set as _set
    from esolangs.languages.painfuck.interpreter import _skip_loop as _skip_loop
    from esolangs.languages.painfuck.interpreter import _State as _State
    from esolangs.languages.painfuck.interpreter import _translate as _translate
    from esolangs.languages.painfuck.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.painfuck.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
