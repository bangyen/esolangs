"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.streetcode.generator import _DOWN as _DOWN
    from esolangs.languages.streetcode.generator import _EAST as _EAST
    from esolangs.languages.streetcode.generator import _FLOOR as _FLOOR
    from esolangs.languages.streetcode.generator import _KERB as _KERB
    from esolangs.languages.streetcode.generator import _READ_RUN as _READ_RUN
    from esolangs.languages.streetcode.generator import _RING_COUNTER as _RING_COUNTER
    from esolangs.languages.streetcode.generator import _RING_ENTRY as _RING_ENTRY
    from esolangs.languages.streetcode.generator import _RING_LAP as _RING_LAP
    from esolangs.languages.streetcode.generator import _RING_PER_LAP as _RING_PER_LAP
    from esolangs.languages.streetcode.generator import _RING_ROWS as _RING_ROWS
    from esolangs.languages.streetcode.generator import _ROOF as _ROOF
    from esolangs.languages.streetcode.generator import _SHARED_ROWS as _SHARED_ROWS
    from esolangs.languages.streetcode.generator import _SILL as _SILL
    from esolangs.languages.streetcode.generator import _STALK as _STALK
    from esolangs.languages.streetcode.generator import _TAIL as _TAIL
    from esolangs.languages.streetcode.generator import (
        _TREE_CACHE_MAX as _TREE_CACHE_MAX,
    )
    from esolangs.languages.streetcode.generator import _UP as _UP
    from esolangs.languages.streetcode.generator import _WEST as _WEST
    from esolangs.languages.streetcode.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.streetcode.generator import _balance as _balance
    from esolangs.languages.streetcode.generator import (
        _streetcode_combine as _streetcode_combine,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_constant as _streetcode_constant,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_flat as _streetcode_flat,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_hallway as _streetcode_hallway,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_hallway_program as _streetcode_hallway_program,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_join as _streetcode_join,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_leaf as _streetcode_leaf,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_lift as _streetcode_lift,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_mouths as _streetcode_mouths,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_narrow as _streetcode_narrow,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_populate as _streetcode_populate,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_quarter_turn as _streetcode_quarter_turn,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_ring as _streetcode_ring,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_room as _streetcode_room,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_rotate as _streetcode_rotate,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_shared as _streetcode_shared,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_shared_kerb as _streetcode_shared_kerb,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_shared_lap as _streetcode_shared_lap,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_shared_programs as _streetcode_shared_programs,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_strip as _streetcode_strip,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_tree as _streetcode_tree,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_tree_memo as _streetcode_tree_memo,
    )
    from esolangs.languages.streetcode.generator import (
        _streetcode_tree_span as _streetcode_tree_span,
    )
    from esolangs.languages.streetcode.generator import streetcode as streetcode

_implementation = importlib.import_module("esolangs.languages.streetcode.generator")
sys.modules[__name__] = _implementation
