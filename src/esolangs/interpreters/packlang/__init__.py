"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.packlang.interpreter import _EXPR_SLOT as _EXPR_SLOT
    from esolangs.languages.packlang.interpreter import _advance as _advance
    from esolangs.languages.packlang.interpreter import _apply as _apply
    from esolangs.languages.packlang.interpreter import _callee as _callee
    from esolangs.languages.packlang.interpreter import _entered as _entered
    from esolangs.languages.packlang.interpreter import _evaluate as _evaluate
    from esolangs.languages.packlang.interpreter import _expression_of as _expression_of
    from esolangs.languages.packlang.interpreter import _Frame as _Frame
    from esolangs.languages.packlang.interpreter import _initial_store as _initial_store
    from esolangs.languages.packlang.interpreter import _Machine as _Machine
    from esolangs.languages.packlang.interpreter import _pending_call as _pending_call
    from esolangs.languages.packlang.interpreter import _resolved as _resolved
    from esolangs.languages.packlang.interpreter import _Slot as _Slot
    from esolangs.languages.packlang.interpreter import _State as _State
    from esolangs.languages.packlang.interpreter import _Store as _Store
    from esolangs.languages.packlang.interpreter import _substitute as _substitute
    from esolangs.languages.packlang.interpreter import _type_of as _type_of
    from esolangs.languages.packlang.interpreter import _write as _write
    from esolangs.languages.packlang.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.packlang.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._lex"] = importlib.import_module(
    "esolangs.languages.packlang.interpreter._lex"
)
sys.modules[__name__ + "._literals"] = importlib.import_module(
    "esolangs.languages.packlang.interpreter._literals"
)
sys.modules[__name__ + "._parse"] = importlib.import_module(
    "esolangs.languages.packlang.interpreter._parse"
)
sys.modules[__name__ + "._scope"] = importlib.import_module(
    "esolangs.languages.packlang.interpreter._scope"
)
sys.modules[__name__ + "._values"] = importlib.import_module(
    "esolangs.languages.packlang.interpreter._values"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
