"""Compatibility import for the generator helper."""

import sys
from typing import TYPE_CHECKING

from esolangs.languages.brainfuck.generator import _binary

if TYPE_CHECKING:
    from esolangs.languages.brainfuck.generator._binary import (
        binary_bank as binary_bank,
    )
    from esolangs.languages.brainfuck.generator._binary import (
        larger_suffix_bank as larger_suffix_bank,
    )

sys.modules[__name__] = _binary
