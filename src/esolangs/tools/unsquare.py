"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.unsquare.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.unsquare.generator import _program as _program
    from esolangs.languages.unsquare.generator import _run as _run
    from esolangs.languages.unsquare.generator import _runs as _runs
    from esolangs.languages.unsquare.generator import _shared_pushes as _shared_pushes
    from esolangs.languages.unsquare.generator import (
        balance_unsquare as balance_unsquare,
    )
    from esolangs.languages.unsquare.generator import unsquare as unsquare

_implementation = importlib.import_module("esolangs.languages.unsquare.generator")
sys.modules[__name__] = _implementation
