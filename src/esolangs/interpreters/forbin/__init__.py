"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.forbin.interpreter import REACHES_IO as REACHES_IO
    from esolangs.languages.forbin.interpreter import _bind as _bind
    from esolangs.languages.forbin.interpreter import _BitReader as _BitReader
    from esolangs.languages.forbin.interpreter import _bound as _bound
    from esolangs.languages.forbin.interpreter import _call as _call
    from esolangs.languages.forbin.interpreter import _Closure as _Closure
    from esolangs.languages.forbin.interpreter import _enter as _enter
    from esolangs.languages.forbin.interpreter import _eval as _eval
    from esolangs.languages.forbin.interpreter import _exec_block as _exec_block
    from esolangs.languages.forbin.interpreter import _exec_stmt as _exec_stmt
    from esolangs.languages.forbin.interpreter import _for_rows as _for_rows
    from esolangs.languages.forbin.interpreter import _Frame as _Frame
    from esolangs.languages.forbin.interpreter import _lookup as _lookup
    from esolangs.languages.forbin.interpreter import _Machine as _Machine
    from esolangs.languages.forbin.interpreter import _run as _run
    from esolangs.languages.forbin.interpreter import (
        _start_statement_call as _start_statement_call,
    )
    from esolangs.languages.forbin.interpreter import _State as _State
    from esolangs.languages.forbin.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.forbin.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._parse"] = importlib.import_module(
    "esolangs.languages.forbin.interpreter._parse"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
