# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
"""Compare bounded two-lane traces with the author-rule model."""

import random

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.streetcode import _Machine
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.streetcode_reference import Rectangle


def check(top, bottom, stdin="", initial=None, bound=100):
    assert len(top) == len(bottom)
    assert bottom[0] == "C"
    wall = "+" + "-" * len(top) + "+"
    rows = (wall, "|" + top + "|", "|" + bottom + "|", wall)
    io = ScriptedIO(stdin)
    machine = _Machine._for_run(list(rows), io)
    model = Rectangle(rows, stdin)
    if initial is not None:
        machine.cells = dict(initial)
        model.cells = dict(initial)
    seen = set()
    for generation in range(bound):
        observed = (
            machine.row,
            machine.col,
            "NESW".index(machine.heading),
            machine.cp,
            tuple(sorted(machine.cells.items())),
            io.position(),
            machine.halted,
        )
        assert observed == model.state(), (rows, generation, observed, model.state())
        assert io.getvalue() == model.output
        assert io.reads == model.reads
        if model.halted:
            return "halted", generation
        if model.state() in seen:
            return "cycle", generation
        seen.add(model.state())
        expected_error = actual_error = None
        try:
            model.step()
        except (HaltError, EOFError) as exc:
            expected_error = type(exc)
        try:
            machine.step()
        except (HaltError, EOFError, OverflowError) as exc:
            actual_error = EOFError if isinstance(exc, EOFError) else type(exc)
        assert actual_error == expected_error, (
            rows,
            initial,
            generation,
            expected_error,
            actual_error,
        )
        if expected_error:
            observed = (
                machine.row,
                machine.col,
                "NESW".index(machine.heading),
                machine.cp,
                tuple(sorted(machine.cells.items())),
                io.position(),
                machine.halted,
            )
            assert observed == model.state()
            assert io.getvalue() == model.output
            return expected_error.__name__, generation
    return "bounded", bound


def random_cases(count):
    rng = random.Random(78016)
    for _ in range(count):
        width = rng.randrange(2, 21)
        top = "".join(rng.choice(" ^~= _IOU;#") for _ in range(width))
        bottom = "C" + "".join(rng.choice(" ^~= _IOU;#") for _ in range(width - 1))
        stdin = "".join(rng.choice("0A\n\x00\U0010ffff") for _ in range(24))
        yield top, bottom, stdin
