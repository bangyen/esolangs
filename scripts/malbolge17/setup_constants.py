"""Preserved uniform words and involutive scalar loads for decoder setup."""

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools.malbolge import _Planner

ALL1, ALL2 = 29524, 59048


def reset_labels(plan: _Planner, all1: int) -> None:
    """Reset the label words, retaining known ALL1 words without touching them."""
    plan.op("*", all1)
    plan.mem[all1] = ALL1
    for cell in range(34, 128):
        if plan.mem.get(cell) == ALL1:
            continue
        plan.op("p", cell)
        plan.op("p", cell)
        plan.mem[cell] = ALL1


def preserve(plan: _Planner, all1: int, all2: int, target: int, zero: int) -> None:
    """Copy the live ALL2 word and clear an unknown word before label reset."""
    assert len({all1, all2, target, zero}) == 4
    plan.op("*", all1)
    plan.mem[all1] = ALL1
    for _ in range(2):
        plan.op("p", target)
    plan.mem[target] = ALL1
    plan.op("*", all2)
    plan.mem[all2] = ALL2
    plan.op("p", target)
    plan.mem[target] = ALL2
    plan.op("*", all1)
    plan.mem[all1] = ALL1
    for _ in range(3):
        plan.op("p", zero)
    plan.mem[zero] = 0


def load(plan: _Planner, cell: int, all2: int) -> None:
    """Load a known word without changing it, through two ALL2 crazy passes."""
    value = plan.mem[cell]
    assert value is not None
    assert cell != all2
    for _ in range(2):
        plan.op("*", all2)
        plan.mem[all2] = ALL2
        plan.op("p", cell)
        value = _crazy(ALL2, value)
        plan.mem[cell] = value
