"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.nocomment.generator import (
        _NOCOMMENT_CHAIN_MIN as _NOCOMMENT_CHAIN_MIN,
    )
    from esolangs.languages.nocomment.generator import (
        _NOCOMMENT_GROUP as _NOCOMMENT_GROUP,
    )
    from esolangs.languages.nocomment.generator import (
        _NOCOMMENT_INPUT as _NOCOMMENT_INPUT,
    )
    from esolangs.languages.nocomment.generator import (
        _NOCOMMENT_STAGE as _NOCOMMENT_STAGE,
    )
    from esolangs.languages.nocomment.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.nocomment.generator import PAIR as PAIR
    from esolangs.languages.nocomment.generator import _group as _group
    from esolangs.languages.nocomment.generator import _mover as _mover
    from esolangs.languages.nocomment.generator import (
        _nocomment_chain as _nocomment_chain,
    )
    from esolangs.languages.nocomment.generator import _program as _program
    from esolangs.languages.nocomment.generator import _projected as _projected
    from esolangs.languages.nocomment.generator import _push as _push
    from esolangs.languages.nocomment.generator import (
        balance_nocomment as balance_nocomment,
    )
    from esolangs.languages.nocomment.generator import nocomment as nocomment

_implementation = importlib.import_module("esolangs.languages.nocomment.generator")
sys.modules[__name__] = _implementation
