"""Execution options follow declarations through opaque call adapters."""

import inspect

import pytest

from esolangs.registry import LANGUAGES
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._execution import interpreter_module, prepare_call


@pytest.mark.parametrize("name", sorted(LANGUAGES))
def test_random_declarations_match_both_execution_entry_points(name):
    module = interpreter_module(name)
    for target in (module.run, module._Machine):
        assert ("rng" in inspect.signature(target).parameters) == LANGUAGES[
            name
        ].runtime.random


@pytest.mark.parametrize(
    "name", [name for name, lang in LANGUAGES.items() if lang.runtime.random]
)
def test_unseeded_runs_leave_randomness_to_the_interpreter(name):
    _, options = prepare_call(name, "x", ExecutionContext())
    assert "rng" not in options
