"""Boolean-function program generators (re-exported from the booleans package).

Each generator builds a program that reads n boolean inputs and prints the
truth-table result for the combination it is given.

The generators live in ``esolangs.tools.booleans``, split by language family
(``register``, ``stack``, ``tape``, ``other``); this module re-exports them
for compatibility.
"""

from esolangs.tools.booleans import *  # noqa: F403  (re-export)
from esolangs.tools.booleans import __all__  # noqa: F401  (re-export)
