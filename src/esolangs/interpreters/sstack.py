"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.sstack.interpreter import _CLOSERS as _CLOSERS
    from esolangs.languages.sstack.interpreter import _NAMES as _NAMES
    from esolangs.languages.sstack.interpreter import _TOKEN as _TOKEN
    from esolangs.languages.sstack.interpreter import _advance as _advance
    from esolangs.languages.sstack.interpreter import _Machine as _Machine
    from esolangs.languages.sstack.interpreter import _Op as _Op
    from esolangs.languages.sstack.interpreter import _parse as _parse
    from esolangs.languages.sstack.interpreter import _Stack as _Stack
    from esolangs.languages.sstack.interpreter import _State as _State
    from esolangs.languages.sstack.interpreter import _top as _top
    from esolangs.languages.sstack.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.sstack.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
