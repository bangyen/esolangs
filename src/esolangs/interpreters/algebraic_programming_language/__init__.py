"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.algebraic_programming_language.interpreter import (
        _arith as _arith,
    )
    from esolangs.languages.algebraic_programming_language.interpreter import (
        _format_float as _format_float,
    )
    from esolangs.languages.algebraic_programming_language.interpreter import (
        _Frame as _Frame,
    )
    from esolangs.languages.algebraic_programming_language.interpreter import (
        _Machine as _Machine,
    )
    from esolangs.languages.algebraic_programming_language.interpreter import (
        _raw_arith as _raw_arith,
    )
    from esolangs.languages.algebraic_programming_language.interpreter import (
        _State as _State,
    )
    from esolangs.languages.algebraic_programming_language.interpreter import (
        _truthy as _truthy,
    )
    from esolangs.languages.algebraic_programming_language.interpreter import run as run

_implementation = importlib.import_module(
    "esolangs.languages.algebraic_programming_language.interpreter"
)
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._parse"] = importlib.import_module(
    "esolangs.languages.algebraic_programming_language.interpreter._parse"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
