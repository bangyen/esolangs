"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.eval.generator import _EVAL_INPUT as _EVAL_INPUT
    from esolangs.languages.eval.generator import _EVAL_READ_STACK as _EVAL_READ_STACK
    from esolangs.languages.eval.generator import _EVAL_TREE_STACK as _EVAL_TREE_STACK
    from esolangs.languages.eval.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.eval.generator import PAIR as PAIR
    from esolangs.languages.eval.generator import _eval_ordered as _eval_ordered
    from esolangs.languages.eval.generator import eval as eval  # noqa: A004

_implementation = importlib.import_module("esolangs.languages.eval.generator")
sys.modules[__name__] = _implementation
