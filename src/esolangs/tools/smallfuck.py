"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.smallfuck.generator import BAND as BAND
    from esolangs.languages.smallfuck.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.smallfuck.generator import PAIR as PAIR
    from esolangs.languages.smallfuck.generator import _balance as _balance
    from esolangs.languages.smallfuck.generator import _Builder as _Builder
    from esolangs.languages.smallfuck.generator import _paired_roots as _paired_roots
    from esolangs.languages.smallfuck.generator import _same_layout as _same_layout
    from esolangs.languages.smallfuck.generator import (
        _smallfuck_ordered as _smallfuck_ordered,
    )
    from esolangs.languages.smallfuck.generator import (
        _smallfuck_tree as _smallfuck_tree,
    )
    from esolangs.languages.smallfuck.generator import _trim_tail as _trim_tail
    from esolangs.languages.smallfuck.generator import smallfuck as smallfuck
    from esolangs.languages.smallfuck.generator import (
        smallfuck_setters as smallfuck_setters,
    )

_implementation = importlib.import_module("esolangs.languages.smallfuck.generator")
sys.modules[__name__] = _implementation
