"""Check the Python sources for duplicated code blocks.

Uses pylint's ``duplicate-code`` checker (R0801), which reports similar
blocks across files, to catch copy-pasted helpers like the bracket matcher
or the OISC memory tokenizer.  Skips cleanly when pylint is not installed,
matching how the other optional-tool checks behave; install with
``pip install pylint`` to enable it.

Exits nonzero when pylint reports a duplicate, so the pre-push hook and CI
catch a regression.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["src/esolangs", "scripts", "tests"]


def main() -> int:
    """Run pylint's duplicate-code check; skip if pylint is missing."""
    if shutil.which("pylint") is None:
        try:
            import pylint  # noqa: F401
        except ImportError:
            print(
                "[skip] duplicate-code check: pylint not installed (pip install pylint)"
            )
            return 0
    cmd = [
        sys.executable,
        "-m",
        "pylint",
        "--disable=all",
        "--enable=duplicate-code",
        "--min-similarity-lines=10",
        "--ignore-imports=yes",
        *TARGETS,
    ]
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode == 0:
        print("duplicate-code check: no similar blocks")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
