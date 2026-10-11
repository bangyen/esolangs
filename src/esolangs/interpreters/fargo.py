"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.fargo.interpreter import _BUILTINS as _BUILTINS
    from esolangs.languages.fargo.interpreter import _PENDING as _PENDING
    from esolangs.languages.fargo.interpreter import _ZERO_WIDTH as _ZERO_WIDTH
    from esolangs.languages.fargo.interpreter import _bare_name as _bare_name
    from esolangs.languages.fargo.interpreter import _Def as _Def
    from esolangs.languages.fargo.interpreter import _Frame as _Frame
    from esolangs.languages.fargo.interpreter import _Func as _Func
    from esolangs.languages.fargo.interpreter import _is_literal as _is_literal
    from esolangs.languages.fargo.interpreter import _Machine as _Machine
    from esolangs.languages.fargo.interpreter import (
        _parse_definition as _parse_definition,
    )
    from esolangs.languages.fargo.interpreter import _parse_program as _parse_program
    from esolangs.languages.fargo.interpreter import _Pending as _Pending
    from esolangs.languages.fargo.interpreter import _State as _State
    from esolangs.languages.fargo.interpreter import _strip_comment as _strip_comment
    from esolangs.languages.fargo.interpreter import _Value as _Value
    from esolangs.languages.fargo.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.fargo.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
