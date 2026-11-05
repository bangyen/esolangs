"""The Forbin suites shared helper: run a program and return what it printed."""

import contextlib

from esolangs.generation.helpers import _validate_truth_table, input_weights
from esolangs.languages.forbin.generator import _build_projected
from esolangs.languages.forbin.interpreter import run
from esolangs.runtime.io import ScriptedIO


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


def _build(truth_table: str, width: int | None, bits: int) -> str:
    """Build the program whose shift register addresses ``bits`` inputs."""
    weights, table = input_weights(truth_table, _validate_truth_table(truth_table))
    return _build_projected(weights, table, width, bits)
