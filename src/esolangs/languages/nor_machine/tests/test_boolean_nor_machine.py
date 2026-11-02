"""Tests for the NOR machine Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(1, 2**2**n - 1)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("NOR machine", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("NOR machine", bits)
        got = esolangs.run("NOR machine", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("NOR machine", got) == table[row], (table, row)


def test_constants_consume_the_queue_then_print_once() -> None:
    _check_single_accumulator_boundaries()

    from esolangs.languages.nor_machine.interpreter import _Machine
    from esolangs.languages.nor_machine.proof_formulas import workspace
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = 2 * n

            def _write(self, value):
                assert self.progress() == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("NOR machine", bit * (1 << n), **options)
                if not options:
                    assert len(program) == n + 4 + 5 * int(bit)
                rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
                for row in rows:
                    stdin = esolangs.encode_inputs(
                        "NOR machine", list(map(int, format(row, f"0{n}b")))
                    )
                    io = ReadFirstIO(stdin)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted and steps < n + 10:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                    assert machine.halted
                    assert io.getvalue() == bit
                    assert steps == n + 4 + 5 * int(bit)
                    assert written.bits <= workspace(n, "".join(program.split()))
    assert (
        sum(len(esolangs.generate("NOR machine", format(v, "08b"))) for v in range(256))
        == 83041
    )


def _check_single_accumulator_boundaries() -> None:
    from esolangs.languages.nor_machine.generator import _low_from_singleton, _Queue
    from esolangs.languages.nor_machine.interpreter import _Machine
    from esolangs.languages.nor_machine.proof_formulas import execution, workspace
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    q = _Queue(0)
    q.names = ["v"]
    _low_from_singleton(q, "v")
    macro = "".join(q.out)
    assert len(macro) == 15
    machine = _Machine(macro, ScriptedIO("37\n"))
    for _ in macro:
        machine.step()
    assert list(machine.queue) == [37, -2]
    assert not machine.halted
    assert machine.io.getvalue() == ""
    for n in (1, 4, 5, 6):
        for ignored in (False, True):
            table = "".join(
                str((row >> int(ignored)).bit_count() % 2) for row in range(1 << n)
            )
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("NOR machine", table, **options)
                commands = "".join(program.split())
                for row in (0, 1, (1 << n) - 1):
                    io = ScriptedIO(
                        esolangs.encode_inputs(
                            "NOR machine", list(map(int, f"{row:0{n}b}"))
                        )
                    )
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= len(commands)
                    assert io.getvalue() == table[row]
                    assert io.progress() == 2 * n
                    assert io.past_end == 0
                    assert steps == len(commands) <= execution(n, commands)
                    assert written.bits <= workspace(n, commands)
