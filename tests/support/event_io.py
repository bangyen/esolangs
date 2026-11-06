"""Scripted I/O guards for read/write ordering."""

from esolangs.runtime.io import ScriptedIO


class EventIO(ScriptedIO):
    """A ``ScriptedIO`` that records each read and write in order."""

    def __init__(self, stdin: str = "") -> None:
        super().__init__(stdin)
        self.events: list[tuple[str, str]] = []

    def print_char(self, char: str) -> None:
        self.events.append(("out", char))
        super().print_char(char)

    def input_char(self, prompt: str = "Input: ") -> int:
        self.events.append(("in", ""))
        return super().input_char(prompt)


class ReadFirstIO(ScriptedIO):
    """Require exactly the expected reads before every write, including empty writes."""

    def __init__(self, stdin: str, *, expected: int) -> None:
        super().__init__(stdin)
        self.expected = expected

    def _write(self, value: object) -> None:
        assert self.reads == self.expected
        super()._write(value)


def assert_falloff(factory, program, n, bit, row, limit, *, early=False):
    """Check each pre-halt boundary, exact reads and output for one row."""
    io = ScriptedIO(f"{row:0{n}b}" + "extra")
    machine = factory(program, io)
    for _ in range(limit):
        if early and machine.halted:
            break
        assert not machine.halted
        machine.step()
    assert machine.halted
    assert io.position() == n
    assert io.getvalue() == bit


def assert_oisc_constants(name, workspace, *, decrement=False, relaxed=False):
    """Run every constant layout and retain each OISC's exact resource checks."""
    import importlib

    import esolangs
    from esolangs.registry import LANGUAGES
    from scripts.benchmark import WrittenState

    slug = LANGUAGES[name].id
    factory = importlib.import_module(f"esolangs.languages.{slug}.interpreter")._Machine
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(name, bit * (1 << n), **options).source
                if decrement:
                    cells = list(map(int, program.split()))
                    assert len(cells) == 3 * n + 9
                    assert all(
                        cells[3 * i : 3 * i + 3] == [-1, 3 * n + 7, 3 * i + 3]
                        for i in range(n)
                    )
                    assert cells[3 * n : 3 * n + 3] == [-2, 3 * n + 6, 3 * n + 3]
                elif not options:
                    assert len(program) == 7 * n + 7
                peak = 0
                commands = n + 1 + (decrement)
                bound = workspace(n, program) if not relaxed or not options else None
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    marker = "Q" if decrement else "7"
                    stdin = esolangs.encode_inputs(name, list(map(int, f"{row:0{n}b}")))
                    io = ReadFirstIO(stdin + marker, expected=n)
                    machine = factory(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(
                        machine, 999 if relaxed else commands, written=written
                    )
                    output = io.getvalue()
                    assert (output.strip() if relaxed else output) == bit
                    assert io.past_end == 0
                    assert io.input_char() == ord(marker)
                    if bound is not None:
                        assert steps == commands
                        assert written.bits <= bound
                        if decrement:
                            assert written.bits == bound
                        peak = max(peak, written.bits)
                if bound is not None:
                    assert peak == bound


def count_steps(machine, cap, *, written=None):
    """Run with the original per-step cap and optional workspace samples."""
    steps = 0
    while not machine.halted:
        machine.step()
        if written is not None:
            written.sample(machine.workspace_snapshot())
        steps += 1
        assert steps <= cap
    return steps
