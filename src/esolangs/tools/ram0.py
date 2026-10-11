"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.ram0.generator import _LEAF as _LEAF
    from esolangs.languages.ram0.generator import _RAM0_INPUT as _RAM0_INPUT
    from esolangs.languages.ram0.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.ram0.generator import PAIR as PAIR
    from esolangs.languages.ram0.generator import _balance as _balance
    from esolangs.languages.ram0.generator import _ram0_nand as _ram0_nand
    from esolangs.languages.ram0.generator import _ram0_ordered as _ram0_ordered
    from esolangs.languages.ram0.generator import _ram0_shared as _ram0_shared
    from esolangs.languages.ram0.generator import _same_layout as _same_layout
    from esolangs.languages.ram0.generator import ram0 as ram0

_implementation = importlib.import_module("esolangs.languages.ram0.generator")
sys.modules[__name__] = _implementation
