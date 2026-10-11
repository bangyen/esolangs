"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bfstack.interpreter import _NEEDS_OPERAND as _NEEDS_OPERAND
    from esolangs.languages.bfstack.interpreter import _advance as _advance
    from esolangs.languages.bfstack.interpreter import _forward_table as _forward_table
    from esolangs.languages.bfstack.interpreter import _Machine as _Machine
    from esolangs.languages.bfstack.interpreter import _needs_operand as _needs_operand
    from esolangs.languages.bfstack.interpreter import _State as _State
    from esolangs.languages.bfstack.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.bfstack.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
