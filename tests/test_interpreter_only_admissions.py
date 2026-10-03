"""Public API and VM integration for the three fame-route admissions."""

import pytest

import esolangs
from esolangs.vm import make_vm


@pytest.mark.parametrize(
    ("language", "code", "stdin", "output"),
    [
        ("HQ9+", "h+q", "unused", "Hello, world!\nh+q"),
        ("Nope.", "", "unused", "Nope."),
        ("Unary", "0" * 108, "Z", "Z"),
    ],
)
def test_api_and_vm(language: str, code: str, stdin: str, output: str) -> None:
    assert esolangs.run(language, code, stdin) == output
    vm = make_vm(language, code, stdin)
    while not vm.halted:
        hash(vm.snapshot())
        vm.step()
    assert vm.output == output
    final = vm.snapshot()
    vm.step()
    assert vm.snapshot() == final
    assert esolangs.describe(language)["boolean_generator"] is False
    with pytest.raises(ValueError, match="no boolean generator"):
        esolangs.generate(language, "01")


def test_unary_generator_refusal_does_not_deny_runtime_input() -> None:
    with pytest.raises(esolangs.ArgumentError, match="generator contracts") as caught:
        esolangs.generate("Unary", "01")
    assert "reads no input" not in str(caught.value)
