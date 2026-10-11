"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.rotfuck.generator import _MAX_PAD as _MAX_PAD
    from esolangs.languages.rotfuck.generator import _PADS as _PADS
    from esolangs.languages.rotfuck.generator import _RADIX_BITS as _RADIX_BITS
    from esolangs.languages.rotfuck.generator import _ROTFUCK_CHAIN as _ROTFUCK_CHAIN
    from esolangs.languages.rotfuck.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.rotfuck.generator import _Builder as _Builder
    from esolangs.languages.rotfuck.generator import _dialect as _dialect
    from esolangs.languages.rotfuck.generator import _groups as _groups
    from esolangs.languages.rotfuck.generator import _pads as _pads
    from esolangs.languages.rotfuck.generator import _parse as _parse
    from esolangs.languages.rotfuck.generator import _program as _program
    from esolangs.languages.rotfuck.generator import _rotfuck_rot as _rotfuck_rot
    from esolangs.languages.rotfuck.generator import _select as _select
    from esolangs.languages.rotfuck.generator import _shows as _shows
    from esolangs.languages.rotfuck.generator import _skip as _skip
    from esolangs.languages.rotfuck.generator import _strides as _strides
    from esolangs.languages.rotfuck.generator import _strip as _strip
    from esolangs.languages.rotfuck.generator import _Tree as _Tree
    from esolangs.languages.rotfuck.generator import (
        _UnplaceableError as _UnplaceableError,
    )
    from esolangs.languages.rotfuck.generator import _walk as _walk
    from esolangs.languages.rotfuck.generator import balance_rotfuck as balance_rotfuck
    from esolangs.languages.rotfuck.generator import rotfuck as rotfuck

_implementation = importlib.import_module("esolangs.languages.rotfuck.generator")
sys.modules[__name__] = _implementation
