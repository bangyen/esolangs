"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.modulous.interpreter import _DISPATCH as _DISPATCH
    from esolangs.languages.modulous.interpreter import _QUOTED as _QUOTED
    from esolangs.languages.modulous.interpreter import _RND_FANOUT as _RND_FANOUT
    from esolangs.languages.modulous.interpreter import _TOKEN as _TOKEN
    from esolangs.languages.modulous.interpreter import _add as _add
    from esolangs.languages.modulous.interpreter import _BranchState as _BranchState
    from esolangs.languages.modulous.interpreter import _Core as _Core
    from esolangs.languages.modulous.interpreter import _dup as _dup
    from esolangs.languages.modulous.interpreter import _end as _end
    from esolangs.languages.modulous.interpreter import _freeze as _freeze
    from esolangs.languages.modulous.interpreter import _FrozenCore as _FrozenCore
    from esolangs.languages.modulous.interpreter import _inp as _inp
    from esolangs.languages.modulous.interpreter import _jmp as _jmp
    from esolangs.languages.modulous.interpreter import _Machine as _Machine
    from esolangs.languages.modulous.interpreter import _named as _named
    from esolangs.languages.modulous.interpreter import _operand as _operand
    from esolangs.languages.modulous.interpreter import _pop as _pop
    from esolangs.languages.modulous.interpreter import _print_value as _print_value
    from esolangs.languages.modulous.interpreter import _prt as _prt
    from esolangs.languages.modulous.interpreter import _psh as _psh
    from esolangs.languages.modulous.interpreter import (
        _reject_stray_text as _reject_stray_text,
    )
    from esolangs.languages.modulous.interpreter import (
        _reject_unknown as _reject_unknown,
    )
    from esolangs.languages.modulous.interpreter import _rnd as _rnd
    from esolangs.languages.modulous.interpreter import _rst as _rst
    from esolangs.languages.modulous.interpreter import _State as _State
    from esolangs.languages.modulous.interpreter import _sub as _sub
    from esolangs.languages.modulous.interpreter import _swp as _swp
    from esolangs.languages.modulous.interpreter import _thaw as _thaw
    from esolangs.languages.modulous.interpreter import _top as _top
    from esolangs.languages.modulous.interpreter import _var_arith as _var_arith
    from esolangs.languages.modulous.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.modulous.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
