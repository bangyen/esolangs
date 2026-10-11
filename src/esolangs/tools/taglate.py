"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.taglate.generator import _SEL1_N2 as _SEL1_N2
    from esolangs.languages.taglate.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.taglate.generator import _balanced as _balanced
    from esolangs.languages.taglate.generator import _even_reduce as _even_reduce
    from esolangs.languages.taglate.generator import _half_select as _half_select
    from esolangs.languages.taglate.generator import _odd_reduce as _odd_reduce
    from esolangs.languages.taglate.generator import _reorder_tt as _reorder_tt
    from esolangs.languages.taglate.generator import _seed_commands as _seed_commands
    from esolangs.languages.taglate.generator import _taglate_raw as _taglate_raw
    from esolangs.languages.taglate.generator import balance_taglate as balance_taglate
    from esolangs.languages.taglate.generator import taglate as taglate

_implementation = importlib.import_module("esolangs.languages.taglate.generator")
sys.modules[__name__] = _implementation
