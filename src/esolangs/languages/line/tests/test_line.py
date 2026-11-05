"""Raw wiki raster fixtures against ordinary integer arithmetic."""

from itertools import product
from pathlib import Path

import pytest

from esolangs.languages.line.interpreter import _execute, _Machine
from esolangs.raster import Raster
from esolangs.runtime.io import ScriptedIO


def test_raw_arithmetic_fixtures():
    """Check both execution paths, input cursor, retained state and post-halt steps."""
    for fixture, operation in (
        ("addition", int.__add__),
        ("multiplication", int.__mul__),
    ):
        path = Path(__file__).parent / "fixtures" / f"{fixture}.png"
        program = Raster.from_png(path.read_bytes())
        for left, right in product((0, 1, 2, 5), repeat=2):
            stdin = f"{left} {right} 99"
            io = ScriptedIO(stdin)
            machine = _Machine(program, io)
            for _ in range(1000):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted, (fixture, left, right)
            expected = str(operation(left, right))
            assert io.getvalue() == expected
            assert io.position() == len(f"{left} {right}")
            assert io.reads == 2
            state = machine.snapshot()
            for _ in range(3):
                machine.step()
                assert machine.snapshot() == state
                assert io.getvalue() == expected
            native = ScriptedIO(stdin)
            _execute(program, native)
            assert (native.getvalue(), native.position(), native.reads) == (
                expected,
                io.position(),
                io.reads,
            )
        with pytest.raises(EOFError):
            _execute(program, ScriptedIO("1"))
