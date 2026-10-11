"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.addsubjump.interpreter import _BUILTINS as _BUILTINS
    from esolangs.languages.addsubjump.interpreter import _CF as _CF
    from esolangs.languages.addsubjump.interpreter import _FUM as _FUM
    from esolangs.languages.addsubjump.interpreter import _IO as _IO
    from esolangs.languages.addsubjump.interpreter import _LABEL as _LABEL
    from esolangs.languages.addsubjump.interpreter import _MAX_MEMORY as _MAX_MEMORY
    from esolangs.languages.addsubjump.interpreter import _NEG as _NEG
    from esolangs.languages.addsubjump.interpreter import _NF as _NF
    from esolangs.languages.addsubjump.interpreter import _ONE as _ONE
    from esolangs.languages.addsubjump.interpreter import _SPECIAL as _SPECIAL
    from esolangs.languages.addsubjump.interpreter import _VF as _VF
    from esolangs.languages.addsubjump.interpreter import _ZERO as _ZERO
    from esolangs.languages.addsubjump.interpreter import _ZF as _ZF
    from esolangs.languages.addsubjump.interpreter import _advance as _advance
    from esolangs.languages.addsubjump.interpreter import _assembly as _assembly
    from esolangs.languages.addsubjump.interpreter import _Cells as _Cells
    from esolangs.languages.addsubjump.interpreter import (
        _defined_labels as _defined_labels,
    )
    from esolangs.languages.addsubjump.interpreter import _expand as _expand
    from esolangs.languages.addsubjump.interpreter import _load as _load
    from esolangs.languages.addsubjump.interpreter import _Machine as _Machine
    from esolangs.languages.addsubjump.interpreter import _Macro as _Macro
    from esolangs.languages.addsubjump.interpreter import _macros as _macros
    from esolangs.languages.addsubjump.interpreter import _operands as _operands
    from esolangs.languages.addsubjump.interpreter import _pack as _pack
    from esolangs.languages.addsubjump.interpreter import _program as _program
    from esolangs.languages.addsubjump.interpreter import _source_lines as _source_lines
    from esolangs.languages.addsubjump.interpreter import _split_labels as _split_labels
    from esolangs.languages.addsubjump.interpreter import _State as _State
    from esolangs.languages.addsubjump.interpreter import _store as _store
    from esolangs.languages.addsubjump.interpreter import _too_large as _too_large
    from esolangs.languages.addsubjump.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.addsubjump.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
