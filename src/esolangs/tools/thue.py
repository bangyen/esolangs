"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.thue.generator import (
        _FOLD_NAME_ALPHABET as _FOLD_NAME_ALPHABET,
    )
    from esolangs.languages.thue.generator import _FOLD_RULES as _FOLD_RULES
    from esolangs.languages.thue.generator import _NAME_ALPHABET as _NAME_ALPHABET
    from esolangs.languages.thue.generator import (
        _QUEUED_NAME_ALPHABET as _QUEUED_NAME_ALPHABET,
    )
    from esolangs.languages.thue.generator import _QUEUED_RULES as _QUEUED_RULES
    from esolangs.languages.thue.generator import _RULES as _RULES
    from esolangs.languages.thue.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.thue.generator import _alphabet as _alphabet
    from esolangs.languages.thue.generator import _chunk_marker as _chunk_marker
    from esolangs.languages.thue.generator import _fold as _fold
    from esolangs.languages.thue.generator import _Layout as _Layout
    from esolangs.languages.thue.generator import _marker_digits as _marker_digits
    from esolangs.languages.thue.generator import _shared_layout as _shared_layout
    from esolangs.languages.thue.generator import _tables as _tables
    from esolangs.languages.thue.generator import _thue_entries as _thue_entries
    from esolangs.languages.thue.generator import _thue_layout as _thue_layout
    from esolangs.languages.thue.generator import _thue_short_tree as _thue_short_tree
    from esolangs.languages.thue.generator import _widest as _widest
    from esolangs.languages.thue.generator import balance_thue as balance_thue
    from esolangs.languages.thue.generator import thue as thue

_implementation = importlib.import_module("esolangs.languages.thue.generator")
sys.modules[__name__] = _implementation
