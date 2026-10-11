"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.collatz_multiverse.interpreter import _LINE as _LINE
    from esolangs.languages.collatz_multiverse.interpreter import _NAME as _NAME
    from esolangs.languages.collatz_multiverse.interpreter import _advance as _advance
    from esolangs.languages.collatz_multiverse.interpreter import _arr_get as _arr_get
    from esolangs.languages.collatz_multiverse.interpreter import _arr_set as _arr_set
    from esolangs.languages.collatz_multiverse.interpreter import _Arrays as _Arrays
    from esolangs.languages.collatz_multiverse.interpreter import _Line as _Line
    from esolangs.languages.collatz_multiverse.interpreter import _Machine as _Machine
    from esolangs.languages.collatz_multiverse.interpreter import _Operand as _Operand
    from esolangs.languages.collatz_multiverse.interpreter import _operand as _operand
    from esolangs.languages.collatz_multiverse.interpreter import _plain as _plain
    from esolangs.languages.collatz_multiverse.interpreter import _reg_get as _reg_get
    from esolangs.languages.collatz_multiverse.interpreter import _reg_set as _reg_set
    from esolangs.languages.collatz_multiverse.interpreter import _Regs as _Regs
    from esolangs.languages.collatz_multiverse.interpreter import _State as _State
    from esolangs.languages.collatz_multiverse.interpreter import run as run

_implementation = importlib.import_module(
    "esolangs.languages.collatz_multiverse.interpreter"
)
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
