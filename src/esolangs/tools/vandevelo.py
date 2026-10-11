"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.vandevelo.generator import _ALPHABET as _ALPHABET
    from esolangs.languages.vandevelo.generator import _CANDIDATES as _CANDIDATES
    from esolangs.languages.vandevelo.generator import _COMPLEMENT as _COMPLEMENT
    from esolangs.languages.vandevelo.generator import _INHERIT as _INHERIT
    from esolangs.languages.vandevelo.generator import _REFRESH as _REFRESH
    from esolangs.languages.vandevelo.generator import _RESERVED as _RESERVED
    from esolangs.languages.vandevelo.generator import _SAMPLES as _SAMPLES
    from esolangs.languages.vandevelo.generator import _SCAN as _SCAN
    from esolangs.languages.vandevelo.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.vandevelo.generator import _affine_coset as _affine_coset
    from esolangs.languages.vandevelo.generator import _assure as _assure
    from esolangs.languages.vandevelo.generator import _balance as _balance
    from esolangs.languages.vandevelo.generator import _bank_cap as _bank_cap
    from esolangs.languages.vandevelo.generator import _best as _best
    from esolangs.languages.vandevelo.generator import _constraints as _constraints
    from esolangs.languages.vandevelo.generator import _echelon as _echelon
    from esolangs.languages.vandevelo.generator import (
        _ensure_popular as _ensure_popular,
    )
    from esolangs.languages.vandevelo.generator import _flips as _flips
    from esolangs.languages.vandevelo.generator import _grow as _grow
    from esolangs.languages.vandevelo.generator import _nearest as _nearest
    from esolangs.languages.vandevelo.generator import _Node as _Node
    from esolangs.languages.vandevelo.generator import _pairs as _pairs
    from esolangs.languages.vandevelo.generator import _Peel as _Peel
    from esolangs.languages.vandevelo.generator import _points as _points
    from esolangs.languages.vandevelo.generator import _pruned as _pruned
    from esolangs.languages.vandevelo.generator import _remove as _remove
    from esolangs.languages.vandevelo.generator import _score as _score
    from esolangs.languages.vandevelo.generator import vandevelo as vandevelo

_implementation = importlib.import_module("esolangs.languages.vandevelo.generator")
sys.modules[__name__] = _implementation
