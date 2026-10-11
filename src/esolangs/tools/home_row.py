"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.home_row.generator import _SETUP as _SETUP
    from esolangs.languages.home_row.generator import HOME_ROW_PAIR as HOME_ROW_PAIR
    from esolangs.languages.home_row.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.home_row.generator import _balance as _balance
    from esolangs.languages.home_row.generator import _program as _program
    from esolangs.languages.home_row.generator import _runs as _runs
    from esolangs.languages.home_row.generator import home_row as home_row

_implementation = importlib.import_module("esolangs.languages.home_row.generator")
sys.modules[__name__] = _implementation
