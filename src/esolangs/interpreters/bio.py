"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bio.interpreter import _COMMAND as _COMMAND
    from esolangs.languages.bio.interpreter import _COMMENT as _COMMENT
    from esolangs.languages.bio.interpreter import _advance as _advance
    from esolangs.languages.bio.interpreter import _bumped as _bumped
    from esolangs.languages.bio.interpreter import _closers as _closers
    from esolangs.languages.bio.interpreter import _Machine as _Machine
    from esolangs.languages.bio.interpreter import _State as _State
    from esolangs.languages.bio.interpreter import parse as parse
    from esolangs.languages.bio.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.bio.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
