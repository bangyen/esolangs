"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.minsky_swap.generator import (
        _MINSKY_SHORT_RMSN_PAIR as _MINSKY_SHORT_RMSN_PAIR,
    )
    from esolangs.languages.minsky_swap.generator import (
        _MINSKY_SMALL_RMSN_PAIR as _MINSKY_SMALL_RMSN_PAIR,
    )
    from esolangs.languages.minsky_swap.generator import _RMSN as _RMSN
    from esolangs.languages.minsky_swap.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.minsky_swap.generator import (
        MINSKY_SWAP_PAIR as MINSKY_SWAP_PAIR,
    )
    from esolangs.languages.minsky_swap.generator import _balance as _balance
    from esolangs.languages.minsky_swap.generator import _same_layout as _same_layout
    from esolangs.languages.minsky_swap.generator import minsky_swap as minsky_swap
    from esolangs.languages.minsky_swap.generator import (
        minsky_swap_setters as minsky_swap_setters,
    )

_implementation = importlib.import_module("esolangs.languages.minsky_swap.generator")
sys.modules[__name__] = _implementation
