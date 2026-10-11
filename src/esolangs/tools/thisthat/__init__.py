"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.thisthat.generator import _DOUBLE as _DOUBLE
    from esolangs.languages.thisthat.generator import _NAME as _NAME
    from esolangs.languages.thisthat.generator import _OPPOSITE as _OPPOSITE
    from esolangs.languages.thisthat.generator import _PORTS as _PORTS
    from esolangs.languages.thisthat.generator import _SINGLE as _SINGLE
    from esolangs.languages.thisthat.generator import _STEP as _STEP
    from esolangs.languages.thisthat.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.thisthat.generator import _balance as _balance
    from esolangs.languages.thisthat.generator import _Builder as _Builder
    from esolangs.languages.thisthat.generator import _deque_plan as _deque_plan
    from esolangs.languages.thisthat.generator import _essential as _essential
    from esolangs.languages.thisthat.generator import _first_axis as _first_axis
    from esolangs.languages.thisthat.generator import _layout as _layout
    from esolangs.languages.thisthat.generator import _narrow_tree as _narrow_tree
    from esolangs.languages.thisthat.generator import _path as _path
    from esolangs.languages.thisthat.generator import _rotate_tree as _rotate_tree
    from esolangs.languages.thisthat.generator import _stream_tree as _stream_tree
    from esolangs.languages.thisthat.generator import _strip_tree as _strip_tree
    from esolangs.languages.thisthat.generator import _tree as _tree
    from esolangs.languages.thisthat.generator import thisthat as thisthat

_implementation = importlib.import_module("esolangs.languages.thisthat.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + "._shared"] = importlib.import_module(
    "esolangs.languages.thisthat.generator._shared"
)
