"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.circuit_diagram.interpreter import (
        _apply_gate as _apply_gate,
    )
    from esolangs.languages.circuit_diagram.interpreter import _compile as _compile
    from esolangs.languages.circuit_diagram.interpreter import _drive as _drive
    from esolangs.languages.circuit_diagram.interpreter import _emitted as _emitted
    from esolangs.languages.circuit_diagram.interpreter import (
        _generation as _generation,
    )
    from esolangs.languages.circuit_diagram.interpreter import _Latches as _Latches
    from esolangs.languages.circuit_diagram.interpreter import _Machine as _Machine
    from esolangs.languages.circuit_diagram.interpreter import _merge as _merge
    from esolangs.languages.circuit_diagram.interpreter import (
        _seconds_since_2000 as _seconds_since_2000,
    )
    from esolangs.languages.circuit_diagram.interpreter import _State as _State
    from esolangs.languages.circuit_diagram.interpreter import _Values as _Values
    from esolangs.languages.circuit_diagram.interpreter import run as run

_implementation = importlib.import_module(
    "esolangs.languages.circuit_diagram.interpreter"
)
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._definitions"] = importlib.import_module(
    "esolangs.languages.circuit_diagram.interpreter._definitions"
)
sys.modules[__name__ + "._functions"] = importlib.import_module(
    "esolangs.languages.circuit_diagram.interpreter._functions"
)
sys.modules[__name__ + "._hints"] = importlib.import_module(
    "esolangs.languages.circuit_diagram.interpreter._hints"
)
sys.modules[__name__ + "._parse"] = importlib.import_module(
    "esolangs.languages.circuit_diagram.interpreter._parse"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="keep")
