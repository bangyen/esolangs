"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.factor.interpreter import _BATCH_BITS as _BATCH_BITS
    from esolangs.languages.factor.interpreter import (
        _EXACT_ISPRIME_LIMIT as _EXACT_ISPRIME_LIMIT,
    )
    from esolangs.languages.factor.interpreter import _RESIDUE as _RESIDUE
    from esolangs.languages.factor.interpreter import _SIEVE_CHUNK as _SIEVE_CHUNK
    from esolangs.languages.factor.interpreter import _factorint as _factorint
    from esolangs.languages.factor.interpreter import _Machine as _Machine
    from esolangs.languages.factor.interpreter import _parse as _parse
    from esolangs.languages.factor.interpreter import _State as _State
    from esolangs.languages.factor.interpreter import decode as decode
    from esolangs.languages.factor.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.factor.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run)
