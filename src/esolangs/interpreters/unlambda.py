"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.unlambda.interpreter import _COMMANDS as _COMMANDS
    from esolangs.languages.unlambda.interpreter import _FAILURE as _FAILURE
    from esolangs.languages.unlambda.interpreter import _SUCCESS as _SUCCESS
    from esolangs.languages.unlambda.interpreter import _advance as _advance
    from esolangs.languages.unlambda.interpreter import _App as _App
    from esolangs.languages.unlambda.interpreter import _Apply as _Apply
    from esolangs.languages.unlambda.interpreter import _apply as _apply
    from esolangs.languages.unlambda.interpreter import _Arg as _Arg
    from esolangs.languages.unlambda.interpreter import _Cmd as _Cmd
    from esolangs.languages.unlambda.interpreter import _combinator as _combinator
    from esolangs.languages.unlambda.interpreter import _Cont as _Cont
    from esolangs.languages.unlambda.interpreter import _Eval as _Eval
    from esolangs.languages.unlambda.interpreter import _Frame as _Frame
    from esolangs.languages.unlambda.interpreter import _Fun as _Fun
    from esolangs.languages.unlambda.interpreter import _Kont as _Kont
    from esolangs.languages.unlambda.interpreter import _Machine as _Machine
    from esolangs.languages.unlambda.interpreter import _parse as _parse
    from esolangs.languages.unlambda.interpreter import _Partial as _Partial
    from esolangs.languages.unlambda.interpreter import _Print as _Print
    from esolangs.languages.unlambda.interpreter import _Promise as _Promise
    from esolangs.languages.unlambda.interpreter import _Query as _Query
    from esolangs.languages.unlambda.interpreter import _Ret as _Ret
    from esolangs.languages.unlambda.interpreter import _State as _State
    from esolangs.languages.unlambda.interpreter import _Task as _Task
    from esolangs.languages.unlambda.interpreter import _Term as _Term
    from esolangs.languages.unlambda.interpreter import _tokens as _tokens
    from esolangs.languages.unlambda.interpreter import _Val as _Val
    from esolangs.languages.unlambda.interpreter import _Value as _Value
    from esolangs.languages.unlambda.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.unlambda.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
