"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.inject.interpreter import _LABEL as _LABEL
    from esolangs.languages.inject.interpreter import _advance as _advance
    from esolangs.languages.inject.interpreter import _begins_block as _begins_block
    from esolangs.languages.inject.interpreter import _contents as _contents
    from esolangs.languages.inject.interpreter import _injected as _injected
    from esolangs.languages.inject.interpreter import _innermost as _innermost
    from esolangs.languages.inject.interpreter import _Machine as _Machine
    from esolangs.languages.inject.interpreter import _replaced as _replaced
    from esolangs.languages.inject.interpreter import _skipped as _skipped
    from esolangs.languages.inject.interpreter import _span as _span
    from esolangs.languages.inject.interpreter import _Spans as _Spans
    from esolangs.languages.inject.interpreter import _spans as _spans
    from esolangs.languages.inject.interpreter import _State as _State
    from esolangs.languages.inject.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.inject.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
