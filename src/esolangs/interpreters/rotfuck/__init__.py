"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.rotfuck.interpreter import _COMMANDS as _COMMANDS
    from esolangs.languages.rotfuck.interpreter import _OPCODES as _OPCODES
    from esolangs.languages.rotfuck.interpreter import _advance as _advance
    from esolangs.languages.rotfuck.interpreter import _at as _at
    from esolangs.languages.rotfuck.interpreter import _backward as _backward
    from esolangs.languages.rotfuck.interpreter import _forward as _forward
    from esolangs.languages.rotfuck.interpreter import _jump as _jump
    from esolangs.languages.rotfuck.interpreter import _Machine as _Machine
    from esolangs.languages.rotfuck.interpreter import _Program as _Program
    from esolangs.languages.rotfuck.interpreter import _State as _State
    from esolangs.languages.rotfuck.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.rotfuck.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._dialect"] = importlib.import_module(
    "esolangs.languages.rotfuck.interpreter._dialect"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
