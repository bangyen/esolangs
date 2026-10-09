"""Vandevelo through the shared API, CLI and machinery."""

from dataclasses import replace

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.registry import LANGUAGES


@pytest.mark.medium
def test_termination_polarity_comes_from_the_registry(monkeypatch) -> None:
    language = LANGUAGES["Vandevelo"]
    program = esolangs.generate("Vandevelo", "0110")
    monkeypatch.setitem(
        LANGUAGES,
        "Vandevelo",
        replace(
            language,
            contract=replace(language.contract, answer_values=("diverges", "halts")),
        ),
    )
    assert _evaluate("Vandevelo", program, inputs=2) == "1001"
