"""Both ancestor walks must obey known call traces, not just agree."""

from collections.abc import Callable

import pytest

from esolangs.languages.forbin.interpreter import _Machine
from esolangs.languages.forbin.tests.test_forbin import walk_until_halt_or_ancestor
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_ancestor


class _Trace:
    def __init__(self, stacks: tuple[tuple[object, ...], ...]) -> None:
        self.stacks = stacks
        self.index = 0

    @property
    def frames(self) -> tuple[object, ...]:
        return self.stacks[self.index]

    @property
    def halted(self) -> bool:
        return self.index == len(self.stacks) - 1

    def step(self) -> None:
        self.index += 1

    def frame_entry_key(self, frame: object) -> object:
        return frame


@pytest.mark.parametrize(
    "walk", [run_until_halt_or_ancestor, walk_until_halt_or_ancestor]
)
@pytest.mark.parametrize(
    ("stacks", "expected"),
    [
        (((),), True),
        ((("main",), ("main", "a"), ("main", "a", "a"), ()), False),
        (
            (("main",), ("main", "a"), ("main", "a", "b"), ("main", "a", "b", "a"), ()),
            False,
        ),
        ((("main",), ("main", "a"), ("main",), ("main", "a"), ()), True),
        # A returned deeper frame must not survive a replacement of its parent.
        (
            (
                ("main",),
                ("main", "a"),
                ("main", "a", "b"),
                ("main",),
                ("main", "b"),
                (),
            ),
            True,
        ),
        (
            (("main",), ("main", ("f", 0, 0)), ("main", ("f", 0, 0), ("f", 1, 0)), ()),
            True,
        ),
        (
            (("main",), ("main", ("f", 0, 0)), ("main", ("f", 0, 0), ("f", 0, 1)), ()),
            True,
        ),
    ],
)
def test_known_call_traces(
    walk: Callable[..., bool], stacks: tuple[tuple[object, ...], ...], *, expected: bool
) -> None:
    machine = _Trace(stacks)
    assert walk(machine) is expected


@pytest.mark.parametrize(
    "walk", [run_until_halt_or_ancestor, walk_until_halt_or_ancestor]
)
def test_push_budget_exhaustion_is_not_a_verdict(walk: Callable[..., bool]) -> None:
    machine = _Trace((("main",), ("main", "a"), ("main", "a", "b"), ()))
    with pytest.raises(TimeoutError, match="undecided"):
        walk(machine, limit=2)


def test_ancestor_key_keeps_captured_mutable_state() -> None:
    """A captured bit changes the recursive call into a terminating one."""
    programs = (
        (
            "maker { x=0; bump { x=!x; return x; } return bump; } "
            "go f { bit=(f 0); for _:bit..0 { return 0; } go f; } "
            "main { go (maker 0); out 0,1,0,0,0,0,0,1; }"
        ),
        (
            "main { x=0; bump { x=!x; return x; } "
            "go x { bit=(bump 0); for _:bit..0 { return 0; } go x; } "
            "go 0; out 0,1,0,0,0,0,0,1; }"
        ),
    )
    for code in programs:
        for walk in (run_until_halt_or_ancestor, walk_until_halt_or_ancestor):
            io = ScriptedIO()
            machine = _Machine(code, io)
            assert walk(machine, limit=8)
            assert io.getvalue() == "A"
