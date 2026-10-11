"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.slow_acv_mammalian.generator import _ARRAYS as _ARRAYS
    from esolangs.languages.slow_acv_mammalian.generator import (
        _EXACT_TAIL as _EXACT_TAIL,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _FREE as _FREE
    from esolangs.languages.slow_acv_mammalian.generator import (
        _GREEDY_COUNTS as _GREEDY_COUNTS,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _GREEDY_MIN as _GREEDY_MIN,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _GREEDY_STEP as _GREEDY_STEP,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _IO_MODULUS as _IO_MODULUS,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _J2 as _J2
    from esolangs.languages.slow_acv_mammalian.generator import _LEAF_UNIT as _LEAF_UNIT
    from esolangs.languages.slow_acv_mammalian.generator import _MODULUS as _MODULUS
    from esolangs.languages.slow_acv_mammalian.generator import _POOLS as _POOLS
    from esolangs.languages.slow_acv_mammalian.generator import _PRINT as _PRINT
    from esolangs.languages.slow_acv_mammalian.generator import (
        _STASH_BYTE as _STASH_BYTE,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _W as _W
    from esolangs.languages.slow_acv_mammalian.generator import _W_INV as _W_INV
    from esolangs.languages.slow_acv_mammalian.generator import _W_STEP as _W_STEP
    from esolangs.languages.slow_acv_mammalian.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.slow_acv_mammalian.generator import _aim as _aim
    from esolangs.languages.slow_acv_mammalian.generator import _apply as _apply
    from esolangs.languages.slow_acv_mammalian.generator import _arm as _arm
    from esolangs.languages.slow_acv_mammalian.generator import _arm_core as _arm_core
    from esolangs.languages.slow_acv_mammalian.generator import (
        _arm_core_len as _arm_core_len,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _build_pool as _build_pool,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _check_merge as _check_merge,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _close_arm as _close_arm
    from esolangs.languages.slow_acv_mammalian.generator import (
        _constant_read as _constant_read,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _dispatch_head as _dispatch_head,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _emit as _emit
    from esolangs.languages.slow_acv_mammalian.generator import (
        _exact_append as _exact_append,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _greedy_advance as _greedy_advance,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _greedy_step_table as _greedy_step_table,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _jump as _jump
    from esolangs.languages.slow_acv_mammalian.generator import _laundered as _laundered
    from esolangs.languages.slow_acv_mammalian.generator import _lead as _lead
    from esolangs.languages.slow_acv_mammalian.generator import _leaf as _leaf
    from esolangs.languages.slow_acv_mammalian.generator import _level as _level
    from esolangs.languages.slow_acv_mammalian.generator import _node as _node
    from esolangs.languages.slow_acv_mammalian.generator import _plant as _plant
    from esolangs.languages.slow_acv_mammalian.generator import _pool_bank as _pool_bank
    from esolangs.languages.slow_acv_mammalian.generator import _pool_plan as _pool_plan
    from esolangs.languages.slow_acv_mammalian.generator import _program as _program
    from esolangs.languages.slow_acv_mammalian.generator import _prologue as _prologue
    from esolangs.languages.slow_acv_mammalian.generator import _replay as _replay
    from esolangs.languages.slow_acv_mammalian.generator import _route as _route
    from esolangs.languages.slow_acv_mammalian.generator import _route_len as _route_len
    from esolangs.languages.slow_acv_mammalian.generator import _seeded as _seeded
    from esolangs.languages.slow_acv_mammalian.generator import _settle as _settle
    from esolangs.languages.slow_acv_mammalian.generator import (
        _stash_chunk as _stash_chunk,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _State as _State
    from esolangs.languages.slow_acv_mammalian.generator import _Sums as _Sums
    from esolangs.languages.slow_acv_mammalian.generator import (
        _trampoline as _trampoline,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _trampoline_255 as _trampoline_255,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _trampoline_255_len as _trampoline_255_len,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _trampoline_len as _trampoline_len,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _try_arm as _try_arm
    from esolangs.languages.slow_acv_mammalian.generator import _tune as _tune
    from esolangs.languages.slow_acv_mammalian.generator import (
        _UnreachableError as _UnreachableError,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _w_exact_chunk as _w_exact_chunk,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        _w_greedy_chunk as _w_greedy_chunk,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _w_raise as _w_raise
    from esolangs.languages.slow_acv_mammalian.generator import (
        _w_raise_len as _w_raise_len,
    )
    from esolangs.languages.slow_acv_mammalian.generator import _weights as _weights
    from esolangs.languages.slow_acv_mammalian.generator import (
        _with_leaves as _with_leaves,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        balance_slow_acv_mammalian as balance_slow_acv_mammalian,
    )
    from esolangs.languages.slow_acv_mammalian.generator import (
        slow_acv_mammalian as slow_acv_mammalian,
    )

_implementation = importlib.import_module(
    "esolangs.languages.slow_acv_mammalian.generator"
)
sys.modules[__name__] = _implementation
