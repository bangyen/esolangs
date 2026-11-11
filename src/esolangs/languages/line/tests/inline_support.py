"""Read-first projected inline trees through native PNG extraction."""

import random

from esolangs.languages.line.generator import balance, line
from esolangs.languages.line.interpreter import _Machine
from esolangs.raster import Raster
from esolangs.runtime.io import ScriptedIO
from scripts.docs.resource_evidence import resource_bounds
from tests.support.generator_support import measure_run


class _ReadFirstIO(ScriptedIO):
    def __init__(self, bits: str) -> None:
        super().__init__(" ".join(bits) + " 9")
        self.expected = 2 * len(bits) - 1

    def print_num(self, num: int) -> None:
        assert self.progress() == self.expected
        super().print_num(num)


def _native(table: str, *, balanced: bool) -> int:
    n = len(table).bit_length() - 1
    image = line(table)
    if balanced:
        image = balance(table, image)
    image = Raster.from_png(image.to_png())
    machine = _Machine(image, _ReadFirstIO("0" * n))
    workspace = resource_bounds("Line")["workspace"].formula
    maximum = 0
    cap = (
        5 * n
        if balanced
        else int(resource_bounds("Line")["execution"].formula(n, table))
    )
    for row, expected in enumerate(table):
        machine.state = (0, 0, 0, ())
        machine.io = _ReadFirstIO(f"{row:0{n}b}")
        steps, written = measure_run(machine, limit=cap)
        assert machine.halted
        assert machine.io.getvalue() == expected
        assert machine.io.input_num() == 9
        assert steps <= cap
        assert written.bits <= workspace(n, table)
        maximum = max(maximum, steps)
    return maximum


def check_inline_readers(*, balanced: bool) -> None:
    """Exercise near-full projections, a generic tree and a shared witness."""
    core = format(random.Random(73041).getrandbits(32), "032b")
    for ignored in (0, 3, 5):
        table = "".join(
            core[int(bits[:ignored] + bits[ignored + 1 :], 2)]
            for bits in (f"{row:06b}" for row in range(64))
        )
        _native(table, balanced=balanced)
    table = format(random.Random(1853).getrandbits(64), "064b")
    commands = _native(table, balanced=balanced)
    assert commands <= 30 if balanced else commands == 20
    parity = "".join(str(row.bit_count() & 1) for row in range(64))
    assert _native(parity, balanced=balanced) <= (30 if balanced else 22)
