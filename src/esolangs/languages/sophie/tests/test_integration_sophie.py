"""Sophie through the shared API, CLI and machinery."""

from typing import Any

import pytest

import esolangs
from esolangs import vm


@pytest.mark.medium
@pytest.mark.parametrize(
    ("detector", "hint"),
    [
        ("run_until_halt_or_all_branches_cycle", "branching_successors"),
        ("run_until_halt_or_ancestor", "frame_entry_key"),
        ("run_until_halt_or_growth", "rightward-growing tape"),
        ("run_until_halt_or_value_growth", "unbounded affine values"),
    ],
)
def test_unsupported_detectors_name_the_needed_capability(detector, hint):
    with pytest.raises(TypeError) as caught:
        getattr(vm, detector)(vm.make_vm("Sophie", ""))
    assert type(caught.value) is TypeError
    assert str(caught.value).startswith("Sophie is not ")
    assert hint in caught.value.__notes__[0]


def test_a_wrapping_language_really_reflows() -> None:
    """Sophie declares `wrap`; the positive control checks it really does."""
    wide = esolangs.generate("Sophie", "0110")
    narrow = esolangs.generate("Sophie", "0110", width=10)
    assert "\n" not in wide
    assert "\n" in narrow
    assert esolangs.describe("Sophie")["width_effect"] == "wrap"


def _bounds(profile: dict[str, Any]) -> None:
    """The construction bounds the resource audit holds this generator to."""
    units = profile["source_units"]
    commands = profile["worst_row_commands"]
    memory = profile["peak_memory_cells"]
    stack = profile["peak_stack_items"]
    # No loop opcode: each executed command advances the source cursor.
    assert commands <= units
    assert memory == 1
    assert stack == 0
    assert profile["peak_control_stack_items"] == 0
    assert profile["peak_machine_bits"] <= 8 + units.bit_length() + 1


@pytest.mark.medium
def test_resource_bounds() -> None:
    """The resource audit counts a UTF-8 byte per source unit."""
    from tests.support.screen_support import audit
    from tests.support.screen_support import resource_corpus as corpus

    result = audit("Sophie", 3, corpus(3)["parity"], _bounds)
    assert result["source_utf8_bits"] == 8 * result["source_units"]
