"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.one_two_three.interpreter import _READ as _READ
    from esolangs.languages.one_two_three.interpreter import _START as _START
    from esolangs.languages.one_two_three.interpreter import _WRITE as _WRITE
    from esolangs.languages.one_two_three.interpreter import _advance as _advance
    from esolangs.languages.one_two_three.interpreter import _Bits as _Bits
    from esolangs.languages.one_two_three.interpreter import _byte_of as _byte_of
    from esolangs.languages.one_two_three.interpreter import _landings as _landings
    from esolangs.languages.one_two_three.interpreter import _Machine as _Machine
    from esolangs.languages.one_two_three.interpreter import _State as _State
    from esolangs.languages.one_two_three.interpreter import _with_byte as _with_byte
    from esolangs.languages.one_two_three.interpreter import run as run

_implementation = importlib.import_module(
    "esolangs.languages.one_two_three.interpreter"
)
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
