"""Befunge through the shared API, CLI and machinery."""

import io
from typing import Any

import pytest

import esolangs
from tests.cli_support import _failure
from tests.interpreters.test_input_convention import assert_reads_tokens_on_one_line


def test_generator_cap_hint_reaches_cli(capsys):
    _, err = _failure(["generate", "Befunge", "0010" * (1 << 12)], capsys)
    assert "fixed 80x25 grid" in err
    assert err.count("hint:") == 1


def test_generator_cap_hint() -> None:
    with pytest.raises(esolangs.GeneratorCapError) as caught:
        esolangs.generate("Befunge", "0010" * (1 << 12))
    assert "fixed 80x25 grid" in caught.value.__notes__[0]


# Isolated cases spawn a worker: the medium band, like test_run_isolated.
@pytest.mark.parametrize(
    "mode", ["normal", "steps", pytest.param("isolated", marks=pytest.mark.medium)]
)
def test_invalid_numeric_input_is_not_mislabeled_as_a_program_error(mode: str) -> None:
    bounds: dict[str, Any] = {}
    if mode == "steps":
        bounds["max_steps"] = 100
    elif mode == "isolated":
        bounds["isolated"] = True
    assert esolangs.run("Befunge", "&.@", stdin=b"-12345", **bounds) == "-12345 "
    with pytest.raises(
        esolangs.ArgumentError, match="input must be an integer"
    ) as error:
        esolangs.run("Befunge", '"A",&.@', stdin=io.StringIO("invalid"), **bounds)
    assert error.value.partial_output == "A"


def test_befunge_grid_refusal_is_catchable() -> None:
    with pytest.raises(esolangs.GeneratorCapError, match="80x25"):
        esolangs.generate("Befunge", "0010" * (1 << 12))


def test_it_reads_numeric_tokens_on_the_same_line() -> None:
    assert_reads_tokens_on_one_line("Befunge")
