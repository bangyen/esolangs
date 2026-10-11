"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.jaune.interpreter import _BARE as _BARE
    from esolangs.languages.jaune.interpreter import _NUMBERED as _NUMBERED
    from esolangs.languages.jaune.interpreter import _READ_MARKER as _READ_MARKER
    from esolangs.languages.jaune.interpreter import _READ_OPERAND as _READ_OPERAND
    from esolangs.languages.jaune.interpreter import _advance as _advance
    from esolangs.languages.jaune.interpreter import _Command as _Command
    from esolangs.languages.jaune.interpreter import _Counted as _Counted
    from esolangs.languages.jaune.interpreter import _CountedOp as _CountedOp
    from esolangs.languages.jaune.interpreter import _Machine as _Machine
    from esolangs.languages.jaune.interpreter import _markers as _markers
    from esolangs.languages.jaune.interpreter import _Numbered as _Numbered
    from esolangs.languages.jaune.interpreter import _NumberedOp as _NumberedOp
    from esolangs.languages.jaune.interpreter import _parse as _parse
    from esolangs.languages.jaune.interpreter import _set as _set
    from esolangs.languages.jaune.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.jaune.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
