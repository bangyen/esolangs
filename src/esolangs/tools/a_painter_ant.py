"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.a_painter_ant.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.a_painter_ant.generator import PAIR as PAIR
    from esolangs.languages.a_painter_ant.generator import _program as _program
    from esolangs.languages.a_painter_ant.generator import (
        a_painter_ant as a_painter_ant,
    )
    from esolangs.languages.a_painter_ant.generator import (
        balance_a_painter_ant as balance_a_painter_ant,
    )

_implementation = importlib.import_module("esolangs.languages.a_painter_ant.generator")
sys.modules[__name__] = _implementation
