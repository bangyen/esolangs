"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.crement.interpreter import _NAME as _NAME
    from esolangs.languages.crement.interpreter import _OPERATOR as _OPERATOR
    from esolangs.languages.crement.interpreter import _TERM as _TERM
    from esolangs.languages.crement.interpreter import _advance as _advance
    from esolangs.languages.crement.interpreter import _decimal as _decimal
    from esolangs.languages.crement.interpreter import _decimal_text as _decimal_text
    from esolangs.languages.crement.interpreter import _Instruction as _Instruction
    from esolangs.languages.crement.interpreter import _Machine as _Machine
    from esolangs.languages.crement.interpreter import _number as _number
    from esolangs.languages.crement.interpreter import _parse as _parse
    from esolangs.languages.crement.interpreter import _source_lines as _source_lines
    from esolangs.languages.crement.interpreter import _State as _State
    from esolangs.languages.crement.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.crement.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
