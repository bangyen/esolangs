"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.smu.interpreter import _BITS as _BITS
    from esolangs.languages.smu.interpreter import _PARENS as _PARENS
    from esolangs.languages.smu.interpreter import _TOKENS as _TOKENS
    from esolangs.languages.smu.interpreter import _advance as _advance
    from esolangs.languages.smu.interpreter import _Effect as _Effect
    from esolangs.languages.smu.interpreter import _Machine as _Machine
    from esolangs.languages.smu.interpreter import literals as literals
    from esolangs.languages.smu.interpreter import preprocess as preprocess
    from esolangs.languages.smu.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.smu.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
