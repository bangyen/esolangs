"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bitdeque.generator import (
        _BITDEQUE_SHORT_PAIR as _BITDEQUE_SHORT_PAIR,
    )
    from esolangs.languages.bitdeque.generator import _PRELUDE_LEN as _PRELUDE_LEN
    from esolangs.languages.bitdeque.generator import _SHORT_BLOCK as _SHORT_BLOCK
    from esolangs.languages.bitdeque.generator import BITDEQUE_PAIR as BITDEQUE_PAIR
    from esolangs.languages.bitdeque.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.bitdeque.generator import _balance as _balance
    from esolangs.languages.bitdeque.generator import _bitdeque as _bitdeque
    from esolangs.languages.bitdeque.generator import (
        _bitdeque_linear as _bitdeque_linear,
    )
    from esolangs.languages.bitdeque.generator import (
        _bitdeque_ordered as _bitdeque_ordered,
    )
    from esolangs.languages.bitdeque.generator import (
        _bitdeque_short_load as _bitdeque_short_load,
    )
    from esolangs.languages.bitdeque.generator import (
        _bitdeque_tokens as _bitdeque_tokens,
    )
    from esolangs.languages.bitdeque.generator import _same_layout as _same_layout
    from esolangs.languages.bitdeque.generator import bitdeque as bitdeque
    from esolangs.languages.bitdeque.generator import (
        bitdeque_setters as bitdeque_setters,
    )

_implementation = importlib.import_module("esolangs.languages.bitdeque.generator")
sys.modules[__name__] = _implementation
