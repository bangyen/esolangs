"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.bfstack.generator import _BLOCK_INPUTS as _BLOCK_INPUTS
    from esolangs.languages.bfstack.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.bfstack.generator import (
        _bfstack_cascade as _bfstack_cascade,
    )
    from esolangs.languages.bfstack.generator import _bfstack_class as _bfstack_class
    from esolangs.languages.bfstack.generator import (
        _bfstack_decoder as _bfstack_decoder,
    )
    from esolangs.languages.bfstack.generator import (
        _bfstack_encoder as _bfstack_encoder,
    )
    from esolangs.languages.bfstack.generator import _bfstack_small as _bfstack_small
    from esolangs.languages.bfstack.generator import _payload as _payload
    from esolangs.languages.bfstack.generator import bfstack as bfstack

_implementation = importlib.import_module("esolangs.languages.bfstack.generator")
sys.modules[__name__] = _implementation
