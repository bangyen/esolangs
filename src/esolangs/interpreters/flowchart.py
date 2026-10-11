"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.flowchart.interpreter import _DOWN as _DOWN
    from esolangs.languages.flowchart.interpreter import _EXITS as _EXITS
    from esolangs.languages.flowchart.interpreter import _HEADINGS as _HEADINGS
    from esolangs.languages.flowchart.interpreter import _LEFT as _LEFT
    from esolangs.languages.flowchart.interpreter import _NODES as _NODES
    from esolangs.languages.flowchart.interpreter import _RIGHT as _RIGHT
    from esolangs.languages.flowchart.interpreter import _UP as _UP
    from esolangs.languages.flowchart.interpreter import _Machine as _Machine
    from esolangs.languages.flowchart.interpreter import _Memory as _Memory
    from esolangs.languages.flowchart.interpreter import _Pointer as _Pointer
    from esolangs.languages.flowchart.interpreter import _Spelling as _Spelling
    from esolangs.languages.flowchart.interpreter import _State as _State
    from esolangs.languages.flowchart.interpreter import _turn_left as _turn_left
    from esolangs.languages.flowchart.interpreter import _turn_right as _turn_right
    from esolangs.languages.flowchart.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.flowchart.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="keep")
