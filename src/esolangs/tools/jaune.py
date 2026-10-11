"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.jaune.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.jaune.generator import _inverted_inputs as _inverted_inputs
    from esolangs.languages.jaune.generator import _jaune_ordered as _jaune_ordered
    from esolangs.languages.jaune.generator import _JauneLabels as _JauneLabels
    from esolangs.languages.jaune.generator import _leaf as _leaf
    from esolangs.languages.jaune.generator import jaune as jaune

_implementation = importlib.import_module("esolangs.languages.jaune.generator")
sys.modules[__name__] = _implementation
