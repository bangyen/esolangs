"""Compatibility import for the generator helper."""

import sys
from typing import TYPE_CHECKING

from esolangs.languages.piet.generator import balance as _implementation

if TYPE_CHECKING:
    from esolangs.languages.piet.generator.balance import (
        _MIN_COLUMNS as _MIN_COLUMNS,
    )
    from esolangs.languages.piet.generator.balance import (
        _POINTER as _POINTER,
    )
    from esolangs.languages.piet.generator.balance import (
        _balanced_plan as _balanced_plan,
    )
    from esolangs.languages.piet.generator.balance import (
        _bounded_operations as _bounded_operations,
    )
    from esolangs.languages.piet.generator.balance import (
        _emit as _emit,
    )
    from esolangs.languages.piet.generator.balance import (
        _Plan as _Plan,
    )
    from esolangs.languages.piet.generator.balance import (
        _plan as _plan,
    )
    from esolangs.languages.piet.generator.balance import (
        _Row as _Row,
    )
    from esolangs.languages.piet.generator.balance import (
        balance as balance,
    )
    from esolangs.languages.piet.generator.balance import (
        folded as folded,
    )

sys.modules[__name__] = _implementation
