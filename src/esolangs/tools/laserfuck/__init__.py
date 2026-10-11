"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.laserfuck.generator import _LASER_BIAS as _LASER_BIAS
    from esolangs.languages.laserfuck.generator import _LASER_FLIP_H as _LASER_FLIP_H
    from esolangs.languages.laserfuck.generator import _LASER_INNER as _LASER_INNER
    from esolangs.languages.laserfuck.generator import _LASER_OUTER as _LASER_OUTER
    from esolangs.languages.laserfuck.generator import _LASER_ROTATE as _LASER_ROTATE
    from esolangs.languages.laserfuck.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.laserfuck.generator import MARGIN as MARGIN
    from esolangs.languages.laserfuck.generator import _LaserBlock as _LaserBlock
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_assemble_reader as _laserfuck_assemble_reader,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_attach_tree as _laserfuck_attach_tree,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_build as _laserfuck_build,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_flip as _laserfuck_flip,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_four_columns as _laserfuck_four_columns,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_join as _laserfuck_join,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_place as _laserfuck_place,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_placements as _laserfuck_placements,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_pool as _laserfuck_pool,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_raise_funnel as _laserfuck_raise_funnel,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_rank as _laserfuck_rank,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_reader as _laserfuck_reader,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_reader_blocks as _laserfuck_reader_blocks,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_reader_candidates as _laserfuck_reader_candidates,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_reads as _laserfuck_reads,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_ring_reader as _laserfuck_ring_reader,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_rotate as _laserfuck_rotate,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_tree as _laserfuck_tree,
    )
    from esolangs.languages.laserfuck.generator import (
        _laserfuck_weighted as _laserfuck_weighted,
    )
    from esolangs.languages.laserfuck.generator import _LaserGrid as _LaserGrid
    from esolangs.languages.laserfuck.generator import _LaserReader as _LaserReader
    from esolangs.languages.laserfuck.generator import _LaserTree as _LaserTree
    from esolangs.languages.laserfuck.generator import (
        _ReaderCandidate as _ReaderCandidate,
    )
    from esolangs.languages.laserfuck.generator import (
        balance_laserfuck as balance_laserfuck,
    )
    from esolangs.languages.laserfuck.generator import laserfuck as laserfuck

_implementation = importlib.import_module("esolangs.languages.laserfuck.generator")
sys.modules[__name__] = _implementation
