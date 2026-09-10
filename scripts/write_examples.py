"""Write the committed examples from their generators.

Every committed example is exactly what its generator produces today: the
boolean programs under ``examples/boolean`` come from the boolean generators.
``tests/scripts/test_examples.py`` asserts that; run this script to refresh
the files after a generator changes.

    python scripts/write_examples.py           # every set
    python scripts/write_examples.py boolean   # just one set
"""

import argparse
import pathlib
import sys
from collections.abc import Iterator

from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

ROOT = pathlib.Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"


def boolean_programs() -> Iterator[tuple[str, str]]:
    """Yield ``(stem, program)`` for every boolean example."""
    for stem, example in sorted(BOOLEAN_EXAMPLES.items()):
        yield stem, example.build()


SETS = {
    "boolean": boolean_programs,
}


def write_set(name: str) -> None:
    """Write one example directory from its generators, reporting each file."""
    directory = EXAMPLES / name
    directory.mkdir(parents=True, exist_ok=True)
    for stem, generated in SETS[name]():
        path = directory / f"{stem}.txt"
        # The file is the generator's output plus a final newline, so it is
        # a well-formed text file; the sync test compares after stripping
        # that newline, exactly as the interpreters do when running it.
        program = generated.rstrip("\n") + "\n"
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        path.write_text(program, encoding="utf-8")
        status = "unchanged" if existing == program else "wrote"
        print(f"{status:9} examples/{name}/{stem}.txt")


def main() -> int:
    """Write every requested example set from its generators."""
    parser = argparse.ArgumentParser(description="Write the committed examples")
    parser.add_argument(
        "sets",
        nargs="*",
        choices=list(SETS),
        # No default: argparse validates a default list against ``choices``
        # as if it were a single value, so an empty ``sets`` means "all".
        help="example sets to write (default: all)",
    )
    args = parser.parse_args()
    for name in args.sets or SETS:
        write_set(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
