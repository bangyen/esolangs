"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.packlang.generator import _BLOCK as _BLOCK
    from esolangs.languages.packlang.generator import _FILL_COST as _FILL_COST
    from esolangs.languages.packlang.generator import _MIN_BLOCK as _MIN_BLOCK
    from esolangs.languages.packlang.generator import _NAME_LEN as _NAME_LEN
    from esolangs.languages.packlang.generator import _WIDTH as _WIDTH
    from esolangs.languages.packlang.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.packlang.generator import _balance_form as _balance_form
    from esolangs.languages.packlang.generator import _blocks as _blocks
    from esolangs.languages.packlang.generator import _counter as _counter
    from esolangs.languages.packlang.generator import _dialect as _dialect
    from esolangs.languages.packlang.generator import _folded as _folded
    from esolangs.languages.packlang.generator import _painted as _painted
    from esolangs.languages.packlang.generator import _short_name as _short_name
    from esolangs.languages.packlang.generator import _writes as _writes
    from esolangs.languages.packlang.generator import (
        balance_packlang as balance_packlang,
    )
    from esolangs.languages.packlang.generator import packlang as packlang

_implementation = importlib.import_module("esolangs.languages.packlang.generator")
sys.modules[__name__] = _implementation
