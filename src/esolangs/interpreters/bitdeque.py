"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bitdeque.interpreter import _COMMANDS as _COMMANDS
    from esolangs.languages.bitdeque.interpreter import _advance as _advance
    from esolangs.languages.bitdeque.interpreter import _Machine as _Machine
    from esolangs.languages.bitdeque.interpreter import (
        _reject_stray_text as _reject_stray_text,
    )
    from esolangs.languages.bitdeque.interpreter import _State as _State
    from esolangs.languages.bitdeque.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.bitdeque.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
