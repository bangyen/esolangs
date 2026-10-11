"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.unlambda.generator import _BOUND as _BOUND
    from esolangs.languages.unlambda.generator import _FORCE_BOUND as _FORCE_BOUND
    from esolangs.languages.unlambda.generator import _INERT as _INERT
    from esolangs.languages.unlambda.generator import _OPEN as _OPEN
    from esolangs.languages.unlambda.generator import _PROMISE as _PROMISE
    from esolangs.languages.unlambda.generator import _REACH as _REACH
    from esolangs.languages.unlambda.generator import _READ as _READ
    from esolangs.languages.unlambda.generator import _SKIP as _SKIP
    from esolangs.languages.unlambda.generator import _SPLIT as _SPLIT
    from esolangs.languages.unlambda.generator import _TEST as _TEST
    from esolangs.languages.unlambda.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.unlambda.generator import _leaf as _leaf
    from esolangs.languages.unlambda.generator import unlambda as unlambda

_implementation = importlib.import_module("esolangs.languages.unlambda.generator")
sys.modules[__name__] = _implementation
