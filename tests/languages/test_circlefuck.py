"""Circlefuck through the shared API, CLI and machinery."""

import warnings

import esolangs
from esolangs import tools as boolean


def test_run_warns_when_input_runs_out() -> None:
    program = boolean.circlefuck("10")  # reads one input bit
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        esolangs.run("Circlefuck", program, stdin="")
