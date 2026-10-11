"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.flowchart.generator import _ANSWER as _ANSWER
    from esolangs.languages.flowchart.generator import (
        _FLOWCHART_PITCH as _FLOWCHART_PITCH,
    )
    from esolangs.languages.flowchart.generator import _SHARE_ROWS as _SHARE_ROWS
    from esolangs.languages.flowchart.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.flowchart.generator import _answer_column as _answer_column
    from esolangs.languages.flowchart.generator import _area as _area
    from esolangs.languages.flowchart.generator import _balance as _balance
    from esolangs.languages.flowchart.generator import (
        _flowchart_cells as _flowchart_cells,
    )
    from esolangs.languages.flowchart.generator import (
        _flowchart_deque as _flowchart_deque,
    )
    from esolangs.languages.flowchart.generator import (
        _flowchart_render as _flowchart_render,
    )
    from esolangs.languages.flowchart.generator import (
        _flowchart_stacked as _flowchart_stacked,
    )
    from esolangs.languages.flowchart.generator import _join_jumps as _join_jumps
    from esolangs.languages.flowchart.generator import _occurrences as _occurrences
    from esolangs.languages.flowchart.generator import _paint as _paint
    from esolangs.languages.flowchart.generator import _plan as _plan
    from esolangs.languages.flowchart.generator import _reads as _reads
    from esolangs.languages.flowchart.generator import _set as _set
    from esolangs.languages.flowchart.generator import flowchart as flowchart

_implementation = importlib.import_module("esolangs.languages.flowchart.generator")
sys.modules[__name__] = _implementation
