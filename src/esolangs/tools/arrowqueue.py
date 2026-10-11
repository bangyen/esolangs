"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.arrowqueue.generator import _DRAINED_RING as _DRAINED_RING
    from esolangs.languages.arrowqueue.generator import _IGNORED as _IGNORED
    from esolangs.languages.arrowqueue.generator import (
        _IGNORED_NARROW as _IGNORED_NARROW,
    )
    from esolangs.languages.arrowqueue.generator import _MIDDLE as _MIDDLE
    from esolangs.languages.arrowqueue.generator import _ROWS as _ROWS
    from esolangs.languages.arrowqueue.generator import _STAGE as _STAGE
    from esolangs.languages.arrowqueue.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.arrowqueue.generator import PAIR as PAIR
    from esolangs.languages.arrowqueue.generator import _balance as _balance
    from esolangs.languages.arrowqueue.generator import _cascade as _cascade
    from esolangs.languages.arrowqueue.generator import (
        _four_column_cascade as _four_column_cascade,
    )
    from esolangs.languages.arrowqueue.generator import _program as _program
    from esolangs.languages.arrowqueue.generator import arrowqueue as arrowqueue

_implementation = importlib.import_module("esolangs.languages.arrowqueue.generator")
sys.modules[__name__] = _implementation
