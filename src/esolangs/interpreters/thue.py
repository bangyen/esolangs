"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.thue.interpreter import _BLOCK as _BLOCK
    from esolangs.languages.thue.interpreter import _GROUP as _GROUP
    from esolangs.languages.thue.interpreter import _INPUT as _INPUT
    from esolangs.languages.thue.interpreter import _OUTPUT as _OUTPUT
    from esolangs.languages.thue.interpreter import _SEPARATOR as _SEPARATOR
    from esolangs.languages.thue.interpreter import _advance as _advance
    from esolangs.languages.thue.interpreter import _cut as _cut
    from esolangs.languages.thue.interpreter import _locate as _locate
    from esolangs.languages.thue.interpreter import _Machine as _Machine
    from esolangs.languages.thue.interpreter import _Match as _Match
    from esolangs.languages.thue.interpreter import _matches as _matches
    from esolangs.languages.thue.interpreter import _parse as _parse
    from esolangs.languages.thue.interpreter import _rewrite as _rewrite
    from esolangs.languages.thue.interpreter import _Rule as _Rule
    from esolangs.languages.thue.interpreter import _separator as _separator
    from esolangs.languages.thue.interpreter import _starts as _starts
    from esolangs.languages.thue.interpreter import _State as _State
    from esolangs.languages.thue.interpreter import _Text as _Text
    from esolangs.languages.thue.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.thue.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
