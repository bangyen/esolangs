"""Compatibility import for the language generator."""

import importlib
import sys
from typing import TYPE_CHECKING

from esolangs.languages.piet import generator

if TYPE_CHECKING:
    from esolangs.languages.piet.generator import (
        _ADD as _ADD,
    )
    from esolangs.languages.piet.generator import (
        _IN_NUMBER as _IN_NUMBER,
    )
    from esolangs.languages.piet.generator import (
        _INITIAL as _INITIAL,
    )
    from esolangs.languages.piet.generator import (
        _MULTIPLY as _MULTIPLY,
    )
    from esolangs.languages.piet.generator import (
        _NOT as _NOT,
    )
    from esolangs.languages.piet.generator import (
        _OUT_NUMBER as _OUT_NUMBER,
    )
    from esolangs.languages.piet.generator import (
        _POP as _POP,
    )
    from esolangs.languages.piet.generator import (
        _PUSH as _PUSH,
    )
    from esolangs.languages.piet.generator import (
        _ROLL as _ROLL,
    )
    from esolangs.languages.piet.generator import (
        _SUBTRACT as _SUBTRACT,
    )
    from esolangs.languages.piet.generator import (
        LANGUAGE as LANGUAGE,
    )
    from esolangs.languages.piet.generator import (
        Change as Change,
    )
    from esolangs.languages.piet.generator import (
        Pixel as Pixel,
    )
    from esolangs.languages.piet.generator import (
        _area as _area,
    )
    from esolangs.languages.piet.generator import (
        _balance as _balance,
    )
    from esolangs.languages.piet.generator import (
        _candidates as _candidates,
    )
    from esolangs.languages.piet.generator import (
        _entries as _entries,
    )
    from esolangs.languages.piet.generator import (
        _generate as _generate,
    )
    from esolangs.languages.piet.generator import (
        _half_lookup as _half_lookup,
    )
    from esolangs.languages.piet.generator import (
        _literal_product as _literal_product,
    )
    from esolangs.languages.piet.generator import (
        _lookup as _lookup,
    )
    from esolangs.languages.piet.generator import (
        _next_colour as _next_colour,
    )
    from esolangs.languages.piet.generator import (
        _Operation as _Operation,
    )
    from esolangs.languages.piet.generator import (
        _operations as _operations,
    )
    from esolangs.languages.piet.generator import (
        _push as _push,
    )
    from esolangs.languages.piet.generator import (
        _row_number as _row_number,
    )
    from esolangs.languages.piet.generator import (
        _select as _select,
    )
    from esolangs.languages.piet.generator import (
        piet as piet,
    )
    from esolangs.languages.piet.generator import (
        strip as strip,
    )

sys.modules[__name__ + ".balance"] = importlib.import_module(
    "esolangs.languages.piet.generator.balance"
)
sys.modules[__name__] = generator
