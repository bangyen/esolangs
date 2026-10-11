"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.one_two_three.generator import _IDLE as _IDLE
    from esolangs.languages.one_two_three.generator import _LAWS as _LAWS
    from esolangs.languages.one_two_three.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.one_two_three.generator import ONE as ONE
    from esolangs.languages.one_two_three.generator import PAIR as PAIR
    from esolangs.languages.one_two_three.generator import ZERO as ZERO
    from esolangs.languages.one_two_three.generator import (
        _construct_small as _construct_small,
    )
    from esolangs.languages.one_two_three.generator import (
        _in_name_order as _in_name_order,
    )
    from esolangs.languages.one_two_three.generator import _Law as _Law
    from esolangs.languages.one_two_three.generator import _separated as _separated
    from esolangs.languages.one_two_three.generator import (
        _verdict_junky as _verdict_junky,
    )
    from esolangs.languages.one_two_three.generator import (
        one_two_three as one_two_three,
    )

_implementation = importlib.import_module("esolangs.languages.one_two_three.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".construction"] = importlib.import_module(
    "esolangs.languages.one_two_three.generator.construction"
)
