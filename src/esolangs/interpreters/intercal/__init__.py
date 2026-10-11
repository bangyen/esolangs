"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.intercal.interpreter import _DIGIT_WORDS as _DIGIT_WORDS
    from esolangs.languages.intercal.interpreter import _DIGITS as _DIGITS
    from esolangs.languages.intercal.interpreter import _NEXT_LIMIT as _NEXT_LIMIT
    from esolangs.languages.intercal.interpreter import _ONESPOT_MAX as _ONESPOT_MAX
    from esolangs.languages.intercal.interpreter import _REVERSED as _REVERSED
    from esolangs.languages.intercal.interpreter import _TWOSPOT_MAX as _TWOSPOT_MAX
    from esolangs.languages.intercal.interpreter import _WIDTH as _WIDTH
    from esolangs.languages.intercal.interpreter import _Array as _Array
    from esolangs.languages.intercal.interpreter import _Draws as _Draws
    from esolangs.languages.intercal.interpreter import _element as _element
    from esolangs.languages.intercal.interpreter import _evaluate as _evaluate
    from esolangs.languages.intercal.interpreter import _expression as _expression
    from esolangs.languages.intercal.interpreter import _freeze as _freeze
    from esolangs.languages.intercal.interpreter import _Machine as _Machine
    from esolangs.languages.intercal.interpreter import _roman as _roman
    from esolangs.languages.intercal.interpreter import _select as _select
    from esolangs.languages.intercal.interpreter import _spread as _spread
    from esolangs.languages.intercal.interpreter import _thaw as _thaw
    from esolangs.languages.intercal.interpreter import _Value as _Value
    from esolangs.languages.intercal.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.intercal.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._parse"] = importlib.import_module(
    "esolangs.languages.intercal.interpreter._parse"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
