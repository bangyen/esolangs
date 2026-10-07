"""The renderer's empty and absent cases."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from esolangs.tools.line import line_boolean
from esolangs.tools.line import render as render_module
from esolangs.tools.line.render import chain


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
        plan = render_module._Plan()  # noqa: SLF001
        assert render_module._subtree_extent(None, plan) == (0, 0, 0, 0)  # noqa: SLF001

    def test_an_absent_arm_takes_the_base_spacing(self) -> None:
        """No arm means no goto corridor to reserve."""
        plan = render_module._Plan()  # noqa: SLF001
        assert render_module._arm_spacing(None, plan) == render_module._BRANCH_SPACING  # noqa: SLF001

    def test_a_real_arm_is_measured(self) -> None:
        """The positive control: a populated arm is not the base spacing."""
        arm = chain("+", "+", "+")
        plan = render_module._Plan()  # noqa: SLF001
        assert render_module._arm_spacing(arm, plan) >= render_module._BRANCH_SPACING  # noqa: SLF001


def test_concurrent_renders_match_serial() -> None:
    """Layout state is per call: lazy rasters render from any thread.

    Compact and loose renders interleaved, since module-global gaps and memo
    once let one thread's render rewrite another's geometry mid-layout.
    """
    jobs = [
        (t, c) for t in ("0110100110010110", "0001011101111111") for c in (True, False)
    ]

    def draw(job: tuple[str, bool]) -> list[bytearray]:
        table, compact = job
        node = line_boolean(table)
        return render_module.render(node, acyclic=True, compact=compact).pixels

    serial = [draw(job) for job in jobs]
    switch = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        with ThreadPoolExecutor(len(jobs)) as pool:
            for _ in range(4):
                drawn = pool.map(draw, jobs)
                bad = [j for j, a, b in zip(jobs, drawn, serial, strict=True) if a != b]
                assert not bad
    finally:
        sys.setswitchinterval(switch)
