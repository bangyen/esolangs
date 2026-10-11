"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.forbin.generator import _BLOCK_BITS as _BLOCK_BITS
    from esolangs.languages.forbin.generator import _FORBIN_ALPHABET as _FORBIN_ALPHABET
    from esolangs.languages.forbin.generator import _FORBIN_RESERVED as _FORBIN_RESERVED
    from esolangs.languages.forbin.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.forbin.generator import _balance as _balance
    from esolangs.languages.forbin.generator import _byte as _byte
    from esolangs.languages.forbin.generator import _forbin_name as _forbin_name
    from esolangs.languages.forbin.generator import _Names as _Names
    from esolangs.languages.forbin.generator import _reads as _reads
    from esolangs.languages.forbin.generator import _register as _register
    from esolangs.languages.forbin.generator import _tree as _tree
    from esolangs.languages.forbin.generator import forbin as forbin

_implementation = importlib.import_module("esolangs.languages.forbin.generator")
sys.modules[__name__] = _implementation
