"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.back.generator import _BACK_INPUT as _BACK_INPUT
    from esolangs.languages.back.generator import _MIRROR as _MIRROR
    from esolangs.languages.back.generator import _WRAP_ROWS as _WRAP_ROWS
    from esolangs.languages.back.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.back.generator import PAIR as PAIR
    from esolangs.languages.back.generator import _back_ordered as _back_ordered
    from esolangs.languages.back.generator import _back_parity as _back_parity
    from esolangs.languages.back.generator import _balance as _balance
    from esolangs.languages.back.generator import _descending_back as _descending_back
    from esolangs.languages.back.generator import _reflect_back as _reflect_back
    from esolangs.languages.back.generator import _render as _render
    from esolangs.languages.back.generator import _same_layout as _same_layout
    from esolangs.languages.back.generator import back as back

_implementation = importlib.import_module("esolangs.languages.back.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._routes"] = importlib.import_module(
    "esolangs.languages.back.generator._routes"
)
