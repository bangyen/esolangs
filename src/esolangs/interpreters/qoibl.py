"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.qoibl.interpreter import _VARIABLES as _VARIABLES
    from esolangs.languages.qoibl.interpreter import INSTRUCTIONS as INSTRUCTIONS
    from esolangs.languages.qoibl.interpreter import OPERATORS as OPERATORS
    from esolangs.languages.qoibl.interpreter import _arithmetic as _arithmetic
    from esolangs.languages.qoibl.interpreter import _compare as _compare
    from esolangs.languages.qoibl.interpreter import _Emit as _Emit
    from esolangs.languages.qoibl.interpreter import _eval as _eval
    from esolangs.languages.qoibl.interpreter import _Machine as _Machine
    from esolangs.languages.qoibl.interpreter import _operands as _operands
    from esolangs.languages.qoibl.interpreter import _Read as _Read
    from esolangs.languages.qoibl.interpreter import _Reading as _Reading
    from esolangs.languages.qoibl.interpreter import _scan as _scan
    from esolangs.languages.qoibl.interpreter import _split as _split
    from esolangs.languages.qoibl.interpreter import _State as _State
    from esolangs.languages.qoibl.interpreter import _steal as _steal
    from esolangs.languages.qoibl.interpreter import _tokenized as _tokenized
    from esolangs.languages.qoibl.interpreter import _variable as _variable
    from esolangs.languages.qoibl.interpreter import _Vars as _Vars
    from esolangs.languages.qoibl.interpreter import run as run
    from esolangs.languages.qoibl.interpreter import tokenize as tokenize

_implementation = importlib.import_module("esolangs.languages.qoibl.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="keep")
