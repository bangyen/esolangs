"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.algebraic_programming_language.generator import (
        _NAMES as _NAMES,
    )
    from esolangs.languages.algebraic_programming_language.generator import _NOT as _NOT
    from esolangs.languages.algebraic_programming_language.generator import (
        _NOT_TIGHT as _NOT_TIGHT,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        LANGUAGE as LANGUAGE,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _apl_narrow_layout as _apl_narrow_layout,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _apl_reduced_ordered as _apl_reduced_ordered,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _apl_repeated_expressions as _apl_repeated_expressions,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _apl_shared_ordered as _apl_shared_ordered,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _apl_short_operators as _apl_short_operators,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _apl_split as _apl_split,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _apl_tree_layout as _apl_tree_layout,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _apl_tree_ordered as _apl_tree_ordered,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _essential as _essential,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _join as _join,
    )
    from esolangs.languages.algebraic_programming_language.generator import _Key as _Key
    from esolangs.languages.algebraic_programming_language.generator import (
        _reads as _reads,
    )
    from esolangs.languages.algebraic_programming_language.generator import _Ref as _Ref
    from esolangs.languages.algebraic_programming_language.generator import (
        _Rope as _Rope,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        _span as _span,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        algebraic_programming_language as algebraic_programming_language,
    )
    from esolangs.languages.algebraic_programming_language.generator import (
        balance_apl as balance_apl,
    )

_implementation = importlib.import_module(
    "esolangs.languages.algebraic_programming_language.generator"
)
sys.modules[__name__] = _implementation
