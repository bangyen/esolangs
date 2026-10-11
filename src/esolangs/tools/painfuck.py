"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.painfuck.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.painfuck.generator import _encode as _encode
    from esolangs.languages.painfuck.generator import _move as _move
    from esolangs.languages.painfuck.generator import (
        _painfuck_ordered as _painfuck_ordered,
    )
    from esolangs.languages.painfuck.generator import (
        _painfuck_shared as _painfuck_shared,
    )
    from esolangs.languages.painfuck.generator import _painfuck_tree as _painfuck_tree
    from esolangs.languages.painfuck.generator import _reach as _reach
    from esolangs.languages.painfuck.generator import painfuck as painfuck

_implementation = importlib.import_module("esolangs.languages.painfuck.generator")
sys.modules[__name__] = _implementation
