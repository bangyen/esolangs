"""Language-specific generator execution helpers."""

from tests.interpreters.runner import run_program


def run_fargo(program: str, inputs: list[str]) -> str:
    """Run a Fargo program, packing ``inputs`` into its one input number."""
    from esolangs.languages.fargo.interpreter import run

    number = int("".join(inputs), 2) if inputs else 0
    return run_program(run, program, f"{number}\n")
