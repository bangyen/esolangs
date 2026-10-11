"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bio.generator import _BIO_DOUBLE as _BIO_DOUBLE
    from esolangs.languages.bio.generator import _BIO_SKIP as _BIO_SKIP
    from esolangs.languages.bio.generator import BIO_PAIR as BIO_PAIR
    from esolangs.languages.bio.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.bio.generator import _bio as _bio
    from esolangs.languages.bio.generator import _same_layout as _same_layout
    from esolangs.languages.bio.generator import balance_bio as balance_bio
    from esolangs.languages.bio.generator import bio as bio

_implementation = importlib.import_module("esolangs.languages.bio.generator")
sys.modules[__name__] = _implementation
