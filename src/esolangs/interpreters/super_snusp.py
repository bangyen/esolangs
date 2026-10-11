"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.super_snusp.interpreter import _DIRECTIONS as _DIRECTIONS
    from esolangs.languages.super_snusp.interpreter import (
        _EQUAL_FANOUT as _EQUAL_FANOUT,
    )
    from esolangs.languages.super_snusp.interpreter import _LURD as _LURD
    from esolangs.languages.super_snusp.interpreter import _RULD as _RULD
    from esolangs.languages.super_snusp.interpreter import _advance as _advance
    from esolangs.languages.super_snusp.interpreter import _Cursor as _Cursor
    from esolangs.languages.super_snusp.interpreter import _Effect as _Effect
    from esolangs.languages.super_snusp.interpreter import _floor_root as _floor_root
    from esolangs.languages.super_snusp.interpreter import _Machine as _Machine
    from esolangs.languages.super_snusp.interpreter import _read as _read
    from esolangs.languages.super_snusp.interpreter import _State as _State
    from esolangs.languages.super_snusp.interpreter import _Tape as _Tape
    from esolangs.languages.super_snusp.interpreter import _top as _top
    from esolangs.languages.super_snusp.interpreter import _write as _write
    from esolangs.languages.super_snusp.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.super_snusp.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="strip")
