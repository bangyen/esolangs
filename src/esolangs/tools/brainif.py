"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.brainif.generator import _LOOP_LEVELS as _LOOP_LEVELS
    from esolangs.languages.brainif.generator import _TREE_LEVELS as _TREE_LEVELS
    from esolangs.languages.brainif.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.brainif.generator import _balance as _balance
    from esolangs.languages.brainif.generator import _brainif_dag as _brainif_dag
    from esolangs.languages.brainif.generator import _brainif_linear as _brainif_linear
    from esolangs.languages.brainif.generator import (
        _brainif_resolve as _brainif_resolve,
    )
    from esolangs.languages.brainif.generator import _brainif_tree as _brainif_tree
    from esolangs.languages.brainif.generator import (
        _brainif_tree_entries as _brainif_tree_entries,
    )
    from esolangs.languages.brainif.generator import (
        _brainif_zero_jumps as _brainif_zero_jumps,
    )
    from esolangs.languages.brainif.generator import _Cmd as _Cmd
    from esolangs.languages.brainif.generator import _emit_loop as _emit_loop
    from esolangs.languages.brainif.generator import _End as _End
    from esolangs.languages.brainif.generator import _Entry as _Entry
    from esolangs.languages.brainif.generator import _GotoOut as _GotoOut
    from esolangs.languages.brainif.generator import _If as _If
    from esolangs.languages.brainif.generator import _MoveLeft as _MoveLeft
    from esolangs.languages.brainif.generator import _Out as _Out
    from esolangs.languages.brainif.generator import (
        _residual_layers as _residual_layers,
    )
    from esolangs.languages.brainif.generator import _Strip as _Strip
    from esolangs.languages.brainif.generator import _top_level as _top_level
    from esolangs.languages.brainif.generator import brainif as brainif

_implementation = importlib.import_module("esolangs.languages.brainif.generator")
sys.modules[__name__] = _implementation
