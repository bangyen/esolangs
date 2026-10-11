"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.super_snusp.generator import (
        _TWO_INPUT_SHORT as _TWO_INPUT_SHORT,
    )
    from esolangs.languages.super_snusp.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.super_snusp.generator import _balance as _balance
    from esolangs.languages.super_snusp.generator import _emit_lookup as _emit_lookup
    from esolangs.languages.super_snusp.generator import (
        _super_snusp_flat as _super_snusp_flat,
    )
    from esolangs.languages.super_snusp.generator import (
        _super_snusp_folded as _super_snusp_folded,
    )
    from esolangs.languages.super_snusp.generator import (
        _super_snusp_layout as _super_snusp_layout,
    )
    from esolangs.languages.super_snusp.generator import (
        _super_snusp_tokens as _super_snusp_tokens,
    )
    from esolangs.languages.super_snusp.generator import (
        balance_super_snusp as balance_super_snusp,
    )
    from esolangs.languages.super_snusp.generator import super_snusp as super_snusp

_implementation = importlib.import_module("esolangs.languages.super_snusp.generator")
sys.modules[__name__] = _implementation
