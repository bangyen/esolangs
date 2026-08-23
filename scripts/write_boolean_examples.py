"""Write examples/boolean from the boolean generators.

Every committed boolean example is exactly what its generator produces
today, the same contract examples/hello-world holds for the text
generators.  ``tests/test_examples.py`` asserts that; run this script to
refresh the files after a generator changes.

    python scripts/write_boolean_examples.py
"""

import pathlib

from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES

ROOT = pathlib.Path(__file__).parents[1]
BOOLEAN_DIR = ROOT / "examples" / "boolean"


def main() -> None:
    """Write every committed boolean example from its generator."""
    BOOLEAN_DIR.mkdir(parents=True, exist_ok=True)
    for stem, example in sorted(BOOLEAN_EXAMPLES.items()):
        path = BOOLEAN_DIR / f"{stem}.txt"
        # The file is the generator's output plus a final newline, so it is
        # a well-formed text file; the sync test compares after stripping
        # that newline, exactly as the interpreters do when running it.
        program = example.build().rstrip("\n") + "\n"
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        path.write_text(program, encoding="utf-8")
        status = "unchanged" if existing == program else "wrote"
        print(f"{status:9} examples/boolean/{stem}.txt")


if __name__ == "__main__":
    main()
