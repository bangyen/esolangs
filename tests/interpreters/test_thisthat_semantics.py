# ruff: noqa: SLF001 - instruction primitives are the semantic test surface.
"""Sparse stacks, snapshots, exhaustive merges, and independent cycles."""

import itertools
import random

import pytest

from esolangs.interpreters.grid_based.thisthat import _Machine, _Pointer
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.thisthat_observer import check
from tests.interpreters.thisthat_reference import Reference


@pytest.mark.parametrize(
    ("axis", "end", "value"),
    list(itertools.product(("row", "column"), ("head", "tail"), (None, 0, 1))),
)
def test_sparse_stack(axis, end, value):
    delta = (0, 1) if axis == "column" else (-1, 0)
    for slots in itertools.product((None, 0, 1), repeat=6):
        cells = {
            (delta[0] * distance, delta[1] * distance): bit
            for distance, bit in enumerate(slots, 1)
            if bit is not None
        }
        cells[2, -2] = 1
        reference = Reference(["▣"])
        reference.cells = dict(cells)
        machine = _Machine(["▣"], ScriptedIO(""))
        machine.cells = dict(cells)
        expected = reference.stack_operation(
            int(axis == "column"), int(end == "tail"), value
        )
        actual = (machine._head if end == "head" else machine._tail)(axis, value)
        assert actual == expected
        assert machine.cells == reference.cells


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("▣◺◺■◧■◧◹◹⬓◇", ""),
        ("▣■⬓⬓◇", ""),
        ("▣─◔─◉", ""),
        ("▣─◇", ""),
        ("▣─◇", "x"),
        ("▣─◇═◯═◇", " 0\n"),
    ],
)
def test_targeted_cycles(source, text):
    result = check([source], text)
    assert result["status"] in ("halted", "error")


def test_program_snapshot_identity():
    machines = [_Machine([source], ScriptedIO("")) for source in ("▣─■═◇", "▣─□═◇")]
    assert machines[0].snapshot() != machines[1].snapshot()
    assert check(["▣─■═◇"])["output"] == "1"
    assert check(["▣─□═◇"])["output"] == "0"


def test_foreign_branch_state_is_rejected():
    machine = _Machine(["▣─■═◇"], ScriptedIO(""))
    other = _Machine(["▣─□═◇"], ScriptedIO(""))
    before = machine.branching_snapshot()
    with pytest.raises(ValueError, match="another thisthat program"):
        machine.branching_successors(other.branching_snapshot(), 1)
    assert machine.branching_snapshot() == before


@pytest.mark.parametrize(
    ("glyph", "occupied", "channel", "value"),
    [
        (glyph, occupied, channel, value)
        for glyph in "◹◺"
        for occupied in (False, True)
        for channel, value in (
            ("execution", None),
            ("data", None),
            ("data", 0),
            ("data", 1),
        )
    ],
)
def test_cursor_moves_with_occupied_destinations(glyph, occupied, channel, value):
    grid = ["  │", f"▣─{glyph}═◇", "  ║"]
    target = (-1, -1) if glyph == "◹" else (1, 1)
    cells = {target: 1} if occupied else {}
    machine = _Machine(grid, ScriptedIO(""))
    machine.cells = dict(cells)
    reference = Reference(grid)
    reference.cells = dict(cells)
    expected = reference.advance(((2, 1), (1, 1), int(channel == "data"), value, False))
    following = []
    machine._advance_one(_Pointer((2, 1), (1, 1), channel, value), following)
    assert following == [
        _Pointer(point, previous, "data" if data else "execution", bit, paused)
        for point, previous, data, bit, paused in expected
    ]
    assert machine.cursor == reference.cursor
    assert machine.cells == reference.cells


def test_cursorless_snapshot_progress():
    class Cursorless(ScriptedIO):
        def position(self):
            return 0

    machine = _Machine(["▣◇"], Cursorless("010"))
    snapshots = {machine.snapshot()}
    for _ in range(3):
        machine._advance_one(_Pointer((1, 0), None), [])
        snapshots.add(machine.snapshot())
    assert len(snapshots) == 4
    assert machine.io.reads == 3


def test_all_merge_permutations():
    left = [_Pointer((2, 0), previous) for previous in ((1, 0), (3, 0), (2, -1))]
    right = [_Pointer((8, 0), previous) for previous in ((7, 0), (9, 0))]
    expected = set()
    grid = ("▣─◘─────◘",)
    for left_pointer, right_pointer in itertools.product(left, right):
        pointers = []
        for chosen, exits in (
            (left_pointer, ((3, 0), (1, 0))),
            (right_pointer, ((7, 0),)),
        ):
            pointers.extend(
                _Pointer(point, chosen.position)
                for point in exits
                if point != chosen.previous
            )
        expected.add((tuple(pointers), (), (0, 0), False, 0, 0, grid))
    assert len(expected) == 6
    for order in itertools.permutations(left + right):
        machine = _Machine(list(grid), ScriptedIO(""))
        machine.pointers = order
        before = machine.branching_snapshot()
        assert set(machine.branching_successors(before, 6)) == expected
        assert machine.branching_snapshot() == before
        with pytest.raises(TimeoutError):
            machine.branching_successors(before, 5)


@pytest.mark.parametrize("shard", range(16))
def test_concurrent_cycle_shard(shard):
    for seed in range(shard, 4000, 16):
        rng = random.Random(177564 + seed)
        alphabet = " " * 48 + "─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬◉◘▲▶▼◀△▷▽◁◯◔◈◇◧⬓◨⬒◹◺◐◑◒◓□■▦"
        lines = ["".join(rng.choice(alphabet) for _ in range(5)) for _ in range(5)]
        for index in rng.sample(range(25), rng.randint(1, 3)):
            y, x = divmod(index, 5)
            lines[y] = lines[y][:x] + "▣" + lines[y][x + 1 :]
        for choice in range(3):
            check(
                lines,
                rng.choice(("", "01", " \n1010", "x")),
                choice,
                bound=40,
                allow_bound=True,
            )
