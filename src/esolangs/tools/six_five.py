"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.six_five.generator import _SIX_FIVE_HELD as _SIX_FIVE_HELD
    from esolangs.languages.six_five.generator import (
        _SIX_FIVE_MAX_LABEL as _SIX_FIVE_MAX_LABEL,
    )
    from esolangs.languages.six_five.generator import (
        _SIX_FIVE_NEGATE as _SIX_FIVE_NEGATE,
    )
    from esolangs.languages.six_five.generator import (
        _SIX_FIVE_NORMALIZE as _SIX_FIVE_NORMALIZE,
    )
    from esolangs.languages.six_five.generator import _SIX_FIVE_TEST as _SIX_FIVE_TEST
    from esolangs.languages.six_five.generator import (
        _SIX_FIVE_TREE_NORMALIZE as _SIX_FIVE_TREE_NORMALIZE,
    )
    from esolangs.languages.six_five.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.six_five.generator import _Layout as _Layout
    from esolangs.languages.six_five.generator import (
        _six_five_chosen as _six_five_chosen,
    )
    from esolangs.languages.six_five.generator import _six_five_const as _six_five_const
    from esolangs.languages.six_five.generator import (
        _six_five_dag_cost as _six_five_dag_cost,
    )
    from esolangs.languages.six_five.generator import (
        _six_five_guarded as _six_five_guarded,
    )
    from esolangs.languages.six_five.generator import (
        _six_five_halves as _six_five_halves,
    )
    from esolangs.languages.six_five.generator import (
        _six_five_hoisted as _six_five_hoisted,
    )
    from esolangs.languages.six_five.generator import (
        _six_five_inverted as _six_five_inverted,
    )
    from esolangs.languages.six_five.generator import _six_five_label as _six_five_label
    from esolangs.languages.six_five.generator import (
        _six_five_markers as _six_five_markers,
    )
    from esolangs.languages.six_five.generator import _six_five_move as _six_five_move
    from esolangs.languages.six_five.generator import (
        _six_five_orders as _six_five_orders,
    )
    from esolangs.languages.six_five.generator import (
        _six_five_preload as _six_five_preload,
    )
    from esolangs.languages.six_five.generator import (
        _six_five_shared as _six_five_shared,
    )
    from esolangs.languages.six_five.generator import (
        _six_five_stream_ordered as _six_five_stream_ordered,
    )
    from esolangs.languages.six_five.generator import _six_five_walk as _six_five_walk
    from esolangs.languages.six_five.generator import six_five as six_five

_implementation = importlib.import_module("esolangs.languages.six_five.generator")
sys.modules[__name__] = _implementation
