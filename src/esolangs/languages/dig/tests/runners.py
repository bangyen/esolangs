"""Language-specific generator execution helpers."""

from tests.generators.boolean_runners import _runner

run_dig = _runner("dig", lines=True, newline=True)
