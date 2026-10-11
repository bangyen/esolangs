"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.clockwise.generator import _CLIMB as _CLIMB
    from esolangs.languages.clockwise.generator import _DESCENT as _DESCENT
    from esolangs.languages.clockwise.generator import _DIGIT as _DIGIT
    from esolangs.languages.clockwise.generator import _READS as _READS
    from esolangs.languages.clockwise.generator import _TABLE_ROWS as _TABLE_ROWS
    from esolangs.languages.clockwise.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.clockwise.generator import _balance as _balance
    from esolangs.languages.clockwise.generator import (
        _clockwise_lean_rotate as _clockwise_lean_rotate,
    )
    from esolangs.languages.clockwise.generator import (
        _clockwise_program as _clockwise_program,
    )
    from esolangs.languages.clockwise.generator import (
        _clockwise_two_columns as _clockwise_two_columns,
    )
    from esolangs.languages.clockwise.generator import _command_ring as _command_ring
    from esolangs.languages.clockwise.generator import _constant_ring as _constant_ring
    from esolangs.languages.clockwise.generator import (
        _coordinate_ring as _coordinate_ring,
    )
    from esolangs.languages.clockwise.generator import _render as _render
    from esolangs.languages.clockwise.generator import clockwise as clockwise

_implementation = importlib.import_module("esolangs.languages.clockwise.generator")
sys.modules[__name__] = _implementation
