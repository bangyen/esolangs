"""BFStack through the shared API, CLI and machinery."""

from typing import Any

import pytest

import esolangs.debugger as debugger_api
from tests.interpreters.test_input_convention import assert_echoes_a_newline


class TestEdges:
    """The bounds and the slot arithmetic, pinned where they turn over."""

    def test_no_input_means_no_input(self) -> None:
        """``stdin`` defaults to nothing, not to something."""
        dbg = debugger_api.make_debugger("brainfuck", ",")
        with pytest.raises(EOFError):
            dbg.step()

    def test_watching_the_cell_just_past_the_tape_is_absent(self) -> None:
        # One past the end, where a widened bound indexes out of range
        # instead of reporting the cell does not exist yet.
        dbg = debugger_api.make_debugger("brainfuck", "+")
        history = dbg.watch_cell(1)
        dbg.step()
        assert history == [None]

    def test_breaking_on_the_cell_just_past_the_tape_never_fires(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+")
        dbg.break_on_cell(1, 0)
        dbg.run()
        assert dbg.halted

    def test_watching_a_slot_below_the_top(self) -> None:
        """Slot 1 is the second value down, not the bottom of the stack."""
        dbg = debugger_api.make_debugger("BFStack", ">+>++>+++")
        history = dbg.watch_stack(1)
        dbg.run()
        assert dbg.stack == [1, 2, 3]
        assert history[-1] == 2

    def test_breaking_on_a_slot_below_the_top(self) -> None:
        dbg = debugger_api.make_debugger("BFStack", ">+>++>+++")
        dbg.break_on_stack(1, 2)
        dbg.run()
        assert not dbg.halted
        assert dbg.stack[-2] == 2

    def test_watching_the_slot_just_past_the_stack_is_absent(self) -> None:
        dbg = debugger_api.make_debugger("BFStack", ">+")
        history = dbg.watch_stack(1)
        dbg.step()
        dbg.step()
        assert history == [None, None]


def test_character_input_preserves_newline() -> None:
    assert_echoes_a_newline("BFStack", ",.")


def _bounds(profile: dict[str, Any]) -> None:
    """The construction bounds the resource audit holds this generator to."""
    n, units = profile["inputs"], profile["source_units"]
    commands = profile["worst_row_commands"]
    memory = profile["peak_memory_cells"]
    stack = profile["peak_stack_items"]
    # Prefix arms cost <100 each. The <=7-bit leaf normalizes <=7
    # bytes, adds <=127 weights and visits <=128 cascade guards;
    # even charging 256 iterations for every final byte loop fits 8192.
    assert commands <= 100 * n + 8192
    assert memory == 0
    assert stack <= 2 * max(n - 7, 0) + 3
    # Each seven-bit cascade nests one loop per listed row, plus its
    # outer loop and payload; each prefix branch adds one live loop.
    assert profile["peak_control_stack_items"] <= max(n - 7, 0) + 2 ** min(n, 7) + 2
    assert profile["peak_integer_bits"] <= max(8, units.bit_length())
    assert profile["peak_machine_bits"] <= (
        8 * (2 * max(n - 7, 0) + 3)
        + (max(n - 7, 0) + 2 ** min(n, 7) + 3) * units.bit_length()
    )


@pytest.mark.medium
def test_resource_bounds() -> None:
    """The resource audit counts a UTF-8 byte per source unit."""
    from tests.screen_support import audit
    from tests.screen_support import resource_corpus as corpus

    result = audit("BFStack", 8, corpus(8)["dense"], _bounds)
    assert result["source_utf8_bits"] == 8 * result["source_units"]
