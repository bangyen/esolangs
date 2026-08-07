"""Text generators (re-exported from the generators package).

The generators live in ``esolangs.tools.generators``, split by language
family; this module re-exports them for compatibility and provides the
``python -m esolangs.tools.generate`` CLI.
"""

import sys

from esolangs.tools.generators import *  # noqa: F403  (re-export)
from esolangs.tools.generators import __all__  # noqa: F401  (re-export)


def main() -> None:
    """Generate a program that outputs the given text for each supported language."""
    from esolangs.registry import GENERATORS  # local import avoids a cycle

    if len(sys.argv) < 2:
        print("usage: python -m esolangs.tools.generate <text>")
        print('example: python -m esolangs.tools.generate "Hello, World!"')
        sys.exit(1)

    text = sys.argv[1]
    for name, gen in GENERATORS.items():
        print(f"--- {name} ---")
        print(gen(text))


if __name__ == "__main__":
    main()
