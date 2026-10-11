"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.polynomial.interpreter import _ARITH as _ARITH
    from esolangs.languages.polynomial.interpreter import _COND as _COND
    from esolangs.languages.polynomial.interpreter import (
        _DENSE_DEGREE_PER_CHAR as _DENSE_DEGREE_PER_CHAR,
    )
    from esolangs.languages.polynomial.interpreter import _advance as _advance
    from esolangs.languages.polynomial.interpreter import (
        _bracket_pairs as _bracket_pairs,
    )
    from esolangs.languages.polynomial.interpreter import _Machine as _Machine
    from esolangs.languages.polynomial.interpreter import (
        _parse_program as _parse_program,
    )
    from esolangs.languages.polynomial.interpreter import _partner as _partner
    from esolangs.languages.polynomial.interpreter import _power as _power
    from esolangs.languages.polynomial.interpreter import _quotient as _quotient
    from esolangs.languages.polynomial.interpreter import _sanitize as _sanitize
    from esolangs.languages.polynomial.interpreter import (
        _sanitize_terms as _sanitize_terms,
    )
    from esolangs.languages.polynomial.interpreter import _State as _State
    from esolangs.languages.polynomial.interpreter import (
        _with_digit_limit as _with_digit_limit,
    )
    from esolangs.languages.polynomial.interpreter import brackets as brackets
    from esolangs.languages.polynomial.interpreter import convert as convert
    from esolangs.languages.polynomial.interpreter import run as run
    from esolangs.languages.polynomial.interpreter import sanitize as sanitize
    from esolangs.languages.polynomial.interpreter import (
        sanitize_terms as sanitize_terms,
    )

_implementation = importlib.import_module("esolangs.languages.polynomial.interpreter")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".roots"] = importlib.import_module(
    "esolangs.languages.polynomial.interpreter.roots"
)

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
