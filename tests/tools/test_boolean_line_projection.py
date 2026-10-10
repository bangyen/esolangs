"""Native raster controls for compact Line input storage."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.line import _Machine
from esolangs.tools.line import balance, line, projected_boolean
from scripts.benchmark import WrittenState


def _lift(core, n, kept):
    return "".join(
        core[
            sum(
                ((row >> (n - 1 - at)) & 1) << (len(kept) - 1 - i)
                for i, at in enumerate(kept)
            )
        ]
        for row in range(1 << n)
    )


def _execute(table, image, rows, trace=None):
    n = len(table).bit_length() - 1
    bound = n + 1 + (3 * n - 2).bit_length() + (n - 1).bit_length()
    bound += (2 * n - 1).bit_length() + sum(
        max(1, c.bit_length()) + 1 for c in range(n)
    )
    vm = _Machine(image, ScriptedIO(""))
    peak = 0
    for row in rows:
        vm.state = (0, 0, 0, ())
        vm.io = ScriptedIO(" ".join(f"{row:0{n}b}"))
        written = WrittenState(vm.snapshot())
        commands = 0
        while not vm.halted and commands <= 5 * n:
            vm.step()
            written.sample(vm.snapshot())
            commands += 1
        assert vm.halted
        assert vm.io.getvalue() == table[row]
        if trace is not None:
            trace.append(vm.io.getvalue())
        assert vm.io.progress() == 2 * n - 1
        assert commands <= 5 * n
        assert written.bits <= bound
        peak = max(peak, commands)
    return peak


@pytest.mark.medium
@pytest.mark.parametrize("kept", [(0, 1, 2), (1, 2, 3), (3, 4, 5), (0, 2, 5)])
@pytest.mark.parametrize("balanced", [False, True])
def test_every_row_with_leading_middle_trailing_and_scattered_ignores(kept, balanced):
    table = _lift("00010111", 6, kept)
    image = line(table)
    if balanced:
        image = balance(table, image)
    _execute(table, image, range(64))


@pytest.mark.medium
@pytest.mark.parametrize("value", ["0", "1"])
def test_constant_loader_keeps_a_fresh_output_cell(value):
    table = value * 64
    _execute(table, line(table), range(64))


@pytest.mark.medium
@pytest.mark.parametrize(
    "kept", [(0, 1, 2, 3), (6, 7, 8, 9), (12, 13, 14, 15), (0, 5, 10, 15)]
)
@pytest.mark.parametrize("seed", [73041, 73042, 73043])
def test_cap_projection_covers_every_kept_row_and_both_ignored_fills(seed, kept):
    rng = random.Random(seed)
    core = "".join(str(rng.randrange(2)) for _ in range(16))
    table = _lift(core, 16, kept)
    rows = []
    ignored_mask = sum(1 << (15 - at) for at in range(16) if at not in kept)
    for row in range(16):
        mapped = sum(((row >> (3 - i)) & 1) << (15 - at) for i, at in enumerate(kept))
        rows.extend((mapped, mapped | ignored_mask))
    _execute(table, line(table), rows)


def test_projection_leaves_fully_essential_trees_to_existing_constructors():
    assert projected_boolean("0110") is None


@pytest.mark.medium
def test_compact_loader_admits_a_shared_return_within_the_original_input_budget():
    from esolangs.tools.line.render import _has_goto
    from esolangs.tools.line.shared import shared_tree

    rng = random.Random(73041)
    residual = "".join(str(rng.randrange(2)) for _ in range(64))
    core = residual * 3 + "0" * 64
    table = _lift(core, 16, tuple(range(8, 16)))
    assert shared_tree(table) is None
    image = line(table)
    assert _has_goto(image._payload)  # noqa: SLF001 - physical sharing control
    _execute(table, image, [row | fill for row in range(256) for fill in (0, 255 << 8)])
