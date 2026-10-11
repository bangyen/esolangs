"""Compatibility import for the language generator."""

import importlib
import sys
from typing import TYPE_CHECKING

from esolangs.languages.brainfuck import generator

if TYPE_CHECKING:
    from esolangs.languages.brainfuck.generator import (
        _LEFT as _LEFT,
    )
    from esolangs.languages.brainfuck.generator import (
        _RIGHT as _RIGHT,
    )
    from esolangs.languages.brainfuck.generator import (
        LANGUAGE as LANGUAGE,
    )
    from esolangs.languages.brainfuck.generator import (
        _affine_stream as _affine_stream,
    )
    from esolangs.languages.brainfuck.generator import (
        _bf_ordered as _bf_ordered,
    )
    from esolangs.languages.brainfuck.generator import (
        bf_tree as bf_tree,
    )
    from esolangs.languages.brainfuck.generator import (
        brainfuck as brainfuck,
    )

sys.modules[__name__ + "._binary"] = importlib.import_module(
    "esolangs.languages.brainfuck.generator._binary"
)
sys.modules[__name__] = generator
