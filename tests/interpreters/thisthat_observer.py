"""Compare independently represented cycles, ports, and machine views."""

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.thisthat import _Machine
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.randomness import FirstDraw
from tests.interpreters.thisthat_reference import Reference


def check(
    lines, text="", choice=0, bound=10000, *, allow_bound=False, pointer_limit=128
):
    reference = Reference(lines, text, choice)
    port = ScriptedIO(text)
    machine = _Machine(lines, port, FirstDraw(choice, rest=choice))
    seen = set()
    for generation in range(bound + 1):
        pointers = tuple(
            (p.position, p.previous, int(p.channel == "data"), p.value, p.paused)
            for p in machine.pointers
        )
        assert pointers == reference.pointers, (
            lines,
            text,
            choice,
            generation,
            pointers,
            reference.pointers,
        )
        expected = (
            reference.pointers,
            tuple(sorted(reference.cells.items())),
            reference.cursor,
            reference.stopped,
            reference.offset,
            reference.bit_reads,
            reference.grid,
        )
        assert (pointers, *machine.snapshot()[1:]) == expected
        first = reference.pointers[0][0] if reference.pointers else None
        assert machine.ip == (() if first is None else (first[1], first[0]))
        assert machine.memory == [
            reference.cells[point] for point in sorted(reference.cells)
        ]
        assert machine.stack == [reference.cursor, *sorted(reference.cells.items())]
        assert machine.halted == reference.halted
        assert (port.position(), port.reads, port.past_end, port.getvalue()) == (
            reference.offset,
            reference.reads,
            reference.eof_reads,
            reference.output,
        )
        if reference.halted:
            return {
                "generations": generation,
                "output": reference.output,
                "reads": reference.reads,
                "status": "halted",
            }
        if expected in seen:
            return {
                "generations": generation,
                "output": reference.output,
                "reads": reference.reads,
                "status": "cycle",
            }
        if allow_bound and len(reference.pointers) > pointer_limit:
            return {
                "generations": generation,
                "status": "pointer_limit",
                "output": reference.output,
                "reads": reference.reads,
            }
        seen.add(expected)
        errors = []
        for vm in (reference, machine):
            try:
                vm.step()
            except HaltError as error:
                errors.append(str(error))
            else:
                errors.append(None)
        assert errors[0] == errors[1], errors
        if errors[0]:
            assert (port.position(), port.reads, port.past_end, port.getvalue()) == (
                reference.offset,
                reference.reads,
                reference.eof_reads,
                reference.output,
            )
            assert machine.cells == reference.cells
            assert machine.cursor == reference.cursor
            return {
                "generations": generation + 1,
                "output": reference.output,
                "reads": reference.reads,
                "status": "error",
                "error": errors[0],
            }
    if allow_bound:
        return {
            "generations": bound,
            "status": "bounded",
            "output": reference.output,
            "reads": reference.reads,
        }
    raise AssertionError("cycle observer bound")
