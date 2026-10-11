"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.slow_acv_mammalian.interpreter import _INS as _INS
    from esolangs.languages.slow_acv_mammalian.interpreter import _OPCODE as _OPCODE
    from esolangs.languages.slow_acv_mammalian.interpreter import _advance as _advance
    from esolangs.languages.slow_acv_mammalian.interpreter import _Arrays as _Arrays
    from esolangs.languages.slow_acv_mammalian.interpreter import _Machine as _Machine
    from esolangs.languages.slow_acv_mammalian.interpreter import _partial as _partial
    from esolangs.languages.slow_acv_mammalian.interpreter import _State as _State
    from esolangs.languages.slow_acv_mammalian.interpreter import _tokens as _tokens
    from esolangs.languages.slow_acv_mammalian.interpreter import _total as _total
    from esolangs.languages.slow_acv_mammalian.interpreter import run as run

_implementation = importlib.import_module(
    "esolangs.languages.slow_acv_mammalian.interpreter"
)
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._dialect"] = importlib.import_module(
    "esolangs.languages.slow_acv_mammalian.interpreter._dialect"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
