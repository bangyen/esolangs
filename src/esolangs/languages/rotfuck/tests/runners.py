"""Language-specific generator execution helpers."""

from tests.generators.boolean_runners import _runner
from tests.interpreters.runner import run_program

run_rotfuck = _runner("rotfuck")


def run_rotfuck_forward(program: str, inputs: list[str]) -> str:
    """Run a ROTfuck program under the forward rotation."""
    from esolangs.languages.rotfuck.interpreter import run as _run

    return run_program(_run, program, "".join(inputs), rotation="forward")
