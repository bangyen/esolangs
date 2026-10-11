"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.line.generator import _GREY_RUN as _GREY_RUN
    from esolangs.languages.line.generator import _SMALL_MAX as _SMALL_MAX
    from esolangs.languages.line.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.line.generator import _generate as _generate
    from esolangs.languages.line.generator import _grey_rows as _grey_rows
    from esolangs.languages.line.generator import _project_loader as _project_loader
    from esolangs.languages.line.generator import _render_node as _render_node
    from esolangs.languages.line.generator import balance as balance
    from esolangs.languages.line.generator import line as line
    from esolangs.languages.line.generator import line_boolean as line_boolean
    from esolangs.languages.line.generator import projected_boolean as projected_boolean

_implementation = importlib.import_module("esolangs.languages.line.generator")
sys.modules[__name__] = _implementation
sys.modules[__name__ + ".render"] = importlib.import_module(
    "esolangs.languages.line.generator.render"
)
sys.modules[__name__ + ".shared"] = importlib.import_module(
    "esolangs.languages.line.generator.shared"
)
sys.modules[__name__ + ".small_tree"] = importlib.import_module(
    "esolangs.languages.line.generator.small_tree"
)
sys.modules[__name__ + ".tree_layout"] = importlib.import_module(
    "esolangs.languages.line.generator.tree_layout"
)
