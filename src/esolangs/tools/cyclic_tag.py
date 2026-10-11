"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.cyclic_tag.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.cyclic_tag.generator import PAIR as PAIR
    from esolangs.languages.cyclic_tag.generator import _program as _program
    from esolangs.languages.cyclic_tag.generator import (
        balance_cyclic_tag as balance_cyclic_tag,
    )
    from esolangs.languages.cyclic_tag.generator import cyclic_tag as cyclic_tag

_implementation = importlib.import_module("esolangs.languages.cyclic_tag.generator")
sys.modules[__name__] = _implementation
