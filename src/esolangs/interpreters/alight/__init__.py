"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.alight.interpreter import _BINARY as _BINARY
    from esolangs.languages.alight.interpreter import _BUILTINS as _BUILTINS
    from esolangs.languages.alight.interpreter import _CLOCKWISE as _CLOCKWISE
    from esolangs.languages.alight.interpreter import _EAST as _EAST
    from esolangs.languages.alight.interpreter import _NORTH as _NORTH
    from esolangs.languages.alight.interpreter import _RESERVED as _RESERVED
    from esolangs.languages.alight.interpreter import _SOUTH as _SOUTH
    from esolangs.languages.alight.interpreter import _SPECIALS as _SPECIALS
    from esolangs.languages.alight.interpreter import _WEST as _WEST
    from esolangs.languages.alight.interpreter import _arith as _arith
    from esolangs.languages.alight.interpreter import _boolean as _boolean
    from esolangs.languages.alight.interpreter import _builtin as _builtin
    from esolangs.languages.alight.interpreter import _command_expr as _command_expr
    from esolangs.languages.alight.interpreter import _compare as _compare
    from esolangs.languages.alight.interpreter import _Expr as _Expr
    from esolangs.languages.alight.interpreter import _find as _find
    from esolangs.languages.alight.interpreter import _find_func as _find_func
    from esolangs.languages.alight.interpreter import (
        _first_call_or_none as _first_call_or_none,
    )
    from esolangs.languages.alight.interpreter import _func_params as _func_params
    from esolangs.languages.alight.interpreter import _Heading as _Heading
    from esolangs.languages.alight.interpreter import _index as _index
    from esolangs.languages.alight.interpreter import _is_call as _is_call
    from esolangs.languages.alight.interpreter import _is_num as _is_num
    from esolangs.languages.alight.interpreter import _list_value as _list_value
    from esolangs.languages.alight.interpreter import _logic as _logic
    from esolangs.languages.alight.interpreter import _Machine as _Machine
    from esolangs.languages.alight.interpreter import _parse_args as _parse_args
    from esolangs.languages.alight.interpreter import _parse_expr as _parse_expr
    from esolangs.languages.alight.interpreter import _parse_number as _parse_number
    from esolangs.languages.alight.interpreter import _parse_operand as _parse_operand
    from esolangs.languages.alight.interpreter import _parse_postfix as _parse_postfix
    from esolangs.languages.alight.interpreter import _Parser as _Parser
    from esolangs.languages.alight.interpreter import _read_word as _read_word
    from esolangs.languages.alight.interpreter import _repeat as _repeat
    from esolangs.languages.alight.interpreter import _replace_first as _replace_first
    from esolangs.languages.alight.interpreter import _scan as _scan
    from esolangs.languages.alight.interpreter import _Special as _Special
    from esolangs.languages.alight.interpreter import _State as _State
    from esolangs.languages.alight.interpreter import _truth as _truth
    from esolangs.languages.alight.interpreter import _turned as _turned
    from esolangs.languages.alight.interpreter import _Value as _Value
    from esolangs.languages.alight.interpreter import _Walker as _Walker
    from esolangs.languages.alight.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.alight.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._dialect"] = importlib.import_module(
    "esolangs.languages.alight.interpreter._dialect"
)
sys.modules[__name__ + "._helpers"] = importlib.import_module(
    "esolangs.languages.alight.interpreter._helpers"
)
sys.modules[__name__ + "._hints"] = importlib.import_module(
    "esolangs.languages.alight.interpreter._hints"
)
sys.modules[__name__ + "._state"] = importlib.import_module(
    "esolangs.languages.alight.interpreter._state"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="strip")
