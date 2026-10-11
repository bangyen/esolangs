"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.taglate.interpreter import _POPS as _POPS
    from esolangs.languages.taglate.interpreter import _PREFIX as _PREFIX
    from esolangs.languages.taglate.interpreter import _SINGLE as _SINGLE
    from esolangs.languages.taglate.interpreter import _SUFFIX as _SUFFIX
    from esolangs.languages.taglate.interpreter import _URL_SAFE as _URL_SAFE
    from esolangs.languages.taglate.interpreter import _advance as _advance
    from esolangs.languages.taglate.interpreter import _consumed as _consumed
    from esolangs.languages.taglate.interpreter import _google_url as _google_url
    from esolangs.languages.taglate.interpreter import _Machine as _Machine
    from esolangs.languages.taglate.interpreter import _match as _match
    from esolangs.languages.taglate.interpreter import _partner as _partner
    from esolangs.languages.taglate.interpreter import _pop as _pop
    from esolangs.languages.taglate.interpreter import _program as _program
    from esolangs.languages.taglate.interpreter import _push as _push
    from esolangs.languages.taglate.interpreter import _State as _State
    from esolangs.languages.taglate.interpreter import _tokens as _tokens
    from esolangs.languages.taglate.interpreter import run as run

_implementation = importlib.import_module("esolangs.languages.taglate.interpreter")
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(_implementation.run, shape="keep")
