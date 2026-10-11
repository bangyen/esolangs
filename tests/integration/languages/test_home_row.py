"""Home Row through the shared API, CLI and machinery."""

import importlib

import pytest

import esolangs
from tests.runtime.io.test_input_encoding import XOR


def test_the_width_applies_once_the_bits_are_in() -> None:
    template = esolangs.generate("Home Row", XOR)
    filled = esolangs.instantiate("Home Row", template, [0, 1], width=10)
    assert max(len(line) for line in filled.splitlines()) <= 10


def test_a_wrapped_instantiation_still_computes_the_table() -> None:
    template = esolangs.generate("Home Row", XOR)
    got = "".join(
        esolangs.run(
            "Home Row",
            esolangs.instantiate("Home Row", template, [a, b], width=10),
            timeout=30,
        )
        for a in (0, 1)
        for b in (0, 1)
    )
    assert got == XOR


def test_internal_spacing_is_still_normalized() -> None:
    """The strip must not have replaced the rule that was already working."""
    assert esolangs.describe("Home  Row")["name"] == "Home Row"


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("esolangs.interpreters.home_row", "esolangs.languages.home_row.interpreter"),
        ("esolangs.tools.home_row", "esolangs.languages.home_row.generator"),
    ],
)
def test_compatibility_imports_share_module_state(legacy, canonical, monkeypatch):
    old = importlib.import_module(legacy)
    new = importlib.import_module(canonical)
    assert old is new
    marker = object()
    monkeypatch.setattr(old, "compatibility_probe", marker, raising=False)
    assert new.compatibility_probe is marker
