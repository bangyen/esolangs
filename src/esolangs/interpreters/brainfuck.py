"""Compatibility import for the language interpreter."""

import sys
from typing import TYPE_CHECKING

from esolangs.languages.brainfuck import interpreter

if TYPE_CHECKING:
    from esolangs.languages.brainfuck.interpreter import (
        _ADD as _ADD,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _CLEAR as _CLEAR,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _CLOSE as _CLOSE,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _INPUT as _INPUT,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _LEFT as _LEFT,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _OPEN as _OPEN,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _OUTPUT as _OUTPUT,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _RIGHT as _RIGHT,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _TRANSFER_RIGHT as _TRANSFER_RIGHT,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _advance as _advance,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _committed as _committed,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _compile as _compile,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _Machine as _Machine,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _Op as _Op,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _State as _State,
    )
    from esolangs.languages.brainfuck.interpreter import (
        _written as _written,
    )
    from esolangs.languages.brainfuck.interpreter import (
        run as run,
    )

sys.modules[__name__] = interpreter

if __name__ == "__main__":
    from esolangs.interpreters._entry import script_main

    script_main(interpreter.run)
