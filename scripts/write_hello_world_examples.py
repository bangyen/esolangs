"""Write examples/hello-world from the text generators.

Every committed hello-world example is exactly what its generator produces
today, the counterpart of ``scripts/write_boolean_examples.py`` for the
text generators.  ``tests/test_examples.py`` asserts that; run this script
to refresh the files after a generator changes.

The programs are wrapped to :data:`esolangs.tools.wrap.DEFAULT_WIDTH`
columns, breaking only between whole commands, so a long one-line program
stays readable in a diff.  Languages whose newlines are semantic (the 2D
grid ones) or that reject them (NoComment) are written unwrapped.

    python scripts/write_hello_world_examples.py
"""

import pathlib

from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import DEFAULT_WIDTH, wrap_program

ROOT = pathlib.Path(__file__).parents[1]
HELLO_DIR = ROOT / "examples" / "hello-world"

TEXT = "Hello, World!"


def main() -> None:
    """Write every committed hello-world example from its generator."""
    HELLO_DIR.mkdir(parents=True, exist_ok=True)
    for lang in sorted(LANGUAGES.values(), key=lambda item: item.name):
        if not (lang.generator and lang.interpreter):
            continue
        stem = lang.name.lower().replace(" ", "-")
        path = HELLO_DIR / f"{stem}.txt"
        # The committed file is the generator's output verbatim -- the
        # sync test compares against exactly this, so the trailing newline
        # the generators already emit is kept rather than re-added.
        program = wrap_program(lang.generator(TEXT), lang.id, DEFAULT_WIDTH)
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        path.write_text(program, encoding="utf-8")
        status = "unchanged" if existing == program else "wrote"
        print(f"{status:9} examples/hello-world/{stem}.txt")


if __name__ == "__main__":
    main()
