"""The renderer's empty and absent cases.

``test_bf_to_line.py`` draws real programs, so every helper here is reached
with something to draw.  What none of it reaches is the degenerate call --
no opcodes, no subtree, no arm -- and those are the arms a hand-built graph
meets first.
"""

from __future__ import annotations

import pytest

from esolangs.line import render as render_module
from esolangs.line.render import chain


class TestChain:
    """``chain`` refuses to build a program out of nothing."""

    def test_no_opcodes_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="at least one opcode"):
            chain()

    def test_one_opcode_is_its_own_head(self) -> None:
        head = chain("+")
        assert head.op == "+"
        assert head.next is None

    def test_opcodes_are_linked_in_order(self) -> None:
        head = chain("+", "-", "o")
        assert [head.op, head.next.op, head.next.next.op] == ["+", "-", "o"]  # type: ignore[union-attr]


class TestMeasuringNothing:
    """An absent subtree and an absent arm both have defined answers."""

    def test_an_absent_subtree_has_no_extent(self) -> None:
        assert render_module._subtree_extent(None) == (0, 0, 0, 0)  # noqa: SLF001

    def test_an_absent_arm_takes_the_base_spacing(self) -> None:
        """No arm means no goto corridor to reserve."""
        assert render_module._arm_spacing(None) == render_module._BRANCH_SPACING  # noqa: SLF001

    def test_a_real_arm_is_measured(self) -> None:
        """The positive control: a populated arm is not the base spacing."""
        arm = chain("+", "+", "+")
        assert render_module._arm_spacing(arm) >= render_module._BRANCH_SPACING  # noqa: SLF001
