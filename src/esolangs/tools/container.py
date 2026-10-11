"""Compatibility import for the language implementation."""

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages.container.generator import _RESERVED as _RESERVED
    from esolangs.languages.container.generator import _TREE_MAX_N as _TREE_MAX_N
    from esolangs.languages.container.generator import LANGUAGE as LANGUAGE
    from esolangs.languages.container.generator import (
        _allocate_names as _allocate_names,
    )
    from esolangs.languages.container.generator import (
        _container_names as _container_names,
    )
    from esolangs.languages.container.generator import (
        _container_plan as _container_plan,
    )
    from esolangs.languages.container.generator import (
        _container_threshold as _container_threshold,
    )
    from esolangs.languages.container.generator import (
        _container_tree as _container_tree,
    )
    from esolangs.languages.container.generator import _free_names as _free_names
    from esolangs.languages.container.generator import _Names as _Names
    from esolangs.languages.container.generator import (
        _narrow_rule_parts as _narrow_rule_parts,
    )
    from esolangs.languages.container.generator import _narrow_rules as _narrow_rules
    from esolangs.languages.container.generator import _Node as _Node
    from esolangs.languages.container.generator import (
        _threshold_deltas as _threshold_deltas,
    )
    from esolangs.languages.container.generator import _TreePlan as _TreePlan
    from esolangs.languages.container.generator import (
        balance_container as balance_container,
    )
    from esolangs.languages.container.generator import container as container

_implementation = importlib.import_module("esolangs.languages.container.generator")
sys.modules[__name__] = _implementation
