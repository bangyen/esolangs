"""Language-specific generator execution helpers."""

from tests.generators.boolean_runners import _stdin
from tests.interpreters.runner import run_program


def run_grapheme(program: str, inputs: list[str]) -> str:
    """Run a Grapheme boolean program on the ``%``/``A`` input alphabet."""
    from esolangs.languages.grapheme.interpreter import run

    alphabet = {"0": "%", "1": "A"}
    return run_program(run, program, _stdin([alphabet[i] for i in inputs]))
