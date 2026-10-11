"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.grapheme.interpreter import _CLOSES as _CLOSES
    from esolangs.languages.grapheme.interpreter import _FUNC as _FUNC
    from esolangs.languages.grapheme.interpreter import _OPENS as _OPENS
    from esolangs.languages.grapheme.interpreter import _advance as _advance
    from esolangs.languages.grapheme.interpreter import _as_num as _as_num
    from esolangs.languages.grapheme.interpreter import _finished as _finished
    from esolangs.languages.grapheme.interpreter import _flush_of as _flush_of
    from esolangs.languages.grapheme.interpreter import _Frame as _Frame
    from esolangs.languages.grapheme.interpreter import _frame as _frame
    from esolangs.languages.grapheme.interpreter import _Function as _Function
    from esolangs.languages.grapheme.interpreter import _int_from as _int_from
    from esolangs.languages.grapheme.interpreter import _Machine as _Machine
    from esolangs.languages.grapheme.interpreter import _pop as _pop
    from esolangs.languages.grapheme.interpreter import _StackFx as _StackFx
    from esolangs.languages.grapheme.interpreter import _StackView as _StackView
    from esolangs.languages.grapheme.interpreter import _State as _State
    from esolangs.languages.grapheme.interpreter import _to_int as _to_int
    from esolangs.languages.grapheme.interpreter import _to_str as _to_str
    from esolangs.languages.grapheme.interpreter import _truthy as _truthy
    from esolangs.languages.grapheme.interpreter import _Value as _Value
    from esolangs.languages.grapheme.interpreter import _Vars as _Vars
    from esolangs.languages.grapheme.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.grapheme.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._dialect"] = importlib.import_module(
    "esolangs.languages.grapheme.interpreter._dialect"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
