"""Compatibility import for the language interpreter."""

import sys
from typing import TYPE_CHECKING

from esolangs.languages.piet import interpreter

if TYPE_CHECKING:
    from esolangs.languages.piet.interpreter import (
        _COLOURS as _COLOURS,
    )
    from esolangs.languages.piet.interpreter import (
        _INTEGER as _INTEGER,
    )
    from esolangs.languages.piet.interpreter import (
        BLACK as BLACK,
    )
    from esolangs.languages.piet.interpreter import (
        WHITE as WHITE,
    )
    from esolangs.languages.piet.interpreter import (
        Pixel as Pixel,
    )
    from esolangs.languages.piet.interpreter import (
        Point as Point,
    )
    from esolangs.languages.piet.interpreter import (
        _advance as _advance,
    )
    from esolangs.languages.piet.interpreter import (
        _binary as _binary,
    )
    from esolangs.languages.piet.interpreter import (
        _colour as _colour,
    )
    from esolangs.languages.piet.interpreter import (
        _command as _command,
    )
    from esolangs.languages.piet.interpreter import (
        _Effect as _Effect,
    )
    from esolangs.languages.piet.interpreter import (
        _Machine as _Machine,
    )
    from esolangs.languages.piet.interpreter import (
        _State as _State,
    )
    from esolangs.languages.piet.interpreter import (
        load_source as load_source,
    )
    from esolangs.languages.piet.interpreter import (
        run as run,
    )
    from esolangs.languages.piet.interpreter import (
        supports_scale as supports_scale,
    )

sys.modules[__name__] = interpreter
