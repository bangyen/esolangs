"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bf_pda.generator import BFPDA_PAIR as BFPDA_PAIR
    from esolangs.languages.bf_pda.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.bf_pda.generator import _bfpda_tree as _bfpda_tree
    from esolangs.languages.bf_pda.generator import _prepare as _prepare
    from esolangs.languages.bf_pda.generator import _reflected as _reflected
    from esolangs.languages.bf_pda.generator import _TreeContext as _TreeContext
    from esolangs.languages.bf_pda.generator import bfpda as bfpda

_implementation = importlib.import_module("esolangs.languages.bf_pda.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._bank"] = importlib.import_module(
    "esolangs.languages.bf_pda.generator._bank"
)
sys.modules[__name__ + "._mixed"] = importlib.import_module(
    "esolangs.languages.bf_pda.generator._mixed"
)
