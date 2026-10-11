"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.malbolge.generator import _F_DECODER as _F_DECODER
    from esolangs.languages.malbolge.generator import _F_DECODER_NOPS as _F_DECODER_NOPS
    from esolangs.languages.malbolge.generator import _F_DECODER_SPAN as _F_DECODER_SPAN
    from esolangs.languages.malbolge.generator import _F_EXTRA as _F_EXTRA
    from esolangs.languages.malbolge.generator import (
        _F_HANDLER_FLOOR as _F_HANDLER_FLOOR,
    )
    from esolangs.languages.malbolge.generator import _F_HUB_A as _F_HUB_A
    from esolangs.languages.malbolge.generator import _F_HUB_CELLS as _F_HUB_CELLS
    from esolangs.languages.malbolge.generator import _F_LEVEL3 as _F_LEVEL3
    from esolangs.languages.malbolge.generator import _F_LEVEL3_SEEDS as _F_LEVEL3_SEEDS
    from esolangs.languages.malbolge.generator import _F_OFFSETS as _F_OFFSETS
    from esolangs.languages.malbolge.generator import _F_PREP as _F_PREP
    from esolangs.languages.malbolge.generator import _F_SEEDS as _F_SEEDS
    from esolangs.languages.malbolge.generator import _F_SEGMENTS as _F_SEGMENTS
    from esolangs.languages.malbolge.generator import _F_SELECT as _F_SELECT
    from esolangs.languages.malbolge.generator import _F_SELECT_PREP as _F_SELECT_PREP
    from esolangs.languages.malbolge.generator import _F_TRAMPOLINES as _F_TRAMPOLINES
    from esolangs.languages.malbolge.generator import _F_WINDOW as _F_WINDOW
    from esolangs.languages.malbolge.generator import _FOURTEEN_N as _FOURTEEN_N
    from esolangs.languages.malbolge.generator import _THIRTEEN_N as _THIRTEEN_N
    from esolangs.languages.malbolge.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.malbolge.generator import MAX_INPUTS as MAX_INPUTS
    from esolangs.languages.malbolge.generator import _f_handler as _f_handler
    from esolangs.languages.malbolge.generator import _f_select as _f_select
    from esolangs.languages.malbolge.generator import _f_tables as _f_tables
    from esolangs.languages.malbolge.generator import _fourteen as _fourteen
    from esolangs.languages.malbolge.generator import (
        _fourteen_program as _fourteen_program,
    )
    from esolangs.languages.malbolge.generator import _Layout as _Layout
    from esolangs.languages.malbolge.generator import _second_pass as _second_pass
    from esolangs.languages.malbolge.generator import _seed_values as _seed_values
    from esolangs.languages.malbolge.generator import _t_place as _t_place
    from esolangs.languages.malbolge.generator import _thirteen as _thirteen
    from esolangs.languages.malbolge.generator import (
        _thirteen_program as _thirteen_program,
    )
    from esolangs.languages.malbolge.generator import _Window as _Window
    from esolangs.languages.malbolge.generator import malbolge as malbolge

_implementation = importlib.import_module("esolangs.languages.malbolge.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".core"] = importlib.import_module(
    "esolangs.languages.malbolge.generator.core"
)
sys.modules[__name__ + ".digits"] = importlib.import_module(
    "esolangs.languages.malbolge.generator.digits"
)
