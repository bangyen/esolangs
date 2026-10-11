"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bitwise_cyclic_tag.generator import _SENTINEL as _SENTINEL
    from esolangs.languages.bitwise_cyclic_tag.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.bitwise_cyclic_tag.generator import PAIR as PAIR
    from esolangs.languages.bitwise_cyclic_tag.generator import _program as _program
    from esolangs.languages.bitwise_cyclic_tag.generator import (
        balance_bitwise_cyclic_tag as balance_bitwise_cyclic_tag,
    )
    from esolangs.languages.bitwise_cyclic_tag.generator import (
        bitwise_cyclic_tag as bitwise_cyclic_tag,
    )

_implementation = importlib.import_module(
    "esolangs.languages.bitwise_cyclic_tag.generator"
)
sys.modules[__name__] = _implementation
