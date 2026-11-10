"""Subleq, the one-instruction computer, with unbounded integer cells.

Memory is a list of integers and is also the program.  The three cells
``A B C`` at ``pc`` mean: ``mem[B] -= mem[A]``, then jump to ``C`` if the
result is not positive, else fall through to ``pc + 3``.  The byte-I/O
dialect reads a byte into ``B`` for ``-1 B C`` and prints ``mem[A]`` for
``A -1 C``, falling through after either.

Negative jumps halt; reads beyond loaded memory yield zero. A jump at or past
the end of memory halts; writes past the end grow memory and reads do not, so
only written cells move that end. Writes are effects so a packed table is not
copied at every arithmetic instruction.

Input/output:
    Byte I/O as above; EOF on a read raises.

Errors:
    ProgramError: Malformed source; a negative data address.
    InputExhaustedError: A read at EOF.
    HaltError: An incomplete instruction fetch.
"""

from collections.abc import Mapping
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.languages.subleq.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime._validate import check_address
from esolangs.runtime.io import IO
from esolangs.runtime.memory import parse_int_memory
from esolangs.runtime.source_hints import syntax_error


def _advance(pc: int, jump: int, minuend: int, subtrahend: int) -> tuple[int, int]:
    """Return the next pc and the difference: jump when it is not positive."""
    result = minuend - subtrahend
    return (jump if result <= 0 else pc + 3), result


_WORKSPACE_MODEL = WorkspaceModel(
    "subleq-v1", ("memory", "instruction", "input_cursor")
)


class _Machine:
    """Self-modifying memory and the address of the next instruction."""

    ip_shape = "opaque"

    def __init__(self, code: str | tuple[int, ...], io: IO) -> None:
        self.cells = parse_int_memory(code) if isinstance(code, str) else list(code)
        self.pc = 0
        self.io = io

    @property
    def halted(self) -> bool:
        return self.pc < 0 or self.pc >= len(self.cells)

    @property
    def ip(self) -> int:
        return self.pc

    @property
    def memory(self) -> list[int]:
        return list(self.cells)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        return _WORKSPACE_MODEL.capture(
            memory=tuple(self.cells),
            instruction=self.pc,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        return (tuple(self.cells), self.pc, self.io.progress())

    def _read(self, address: int) -> int:
        if address < 0:
            raise syntax_error(
                f"invalid Subleq data address {address}",
                "use a nonnegative data address; -1 is reserved for I/O",
            )
        return self.cells[address] if address < len(self.cells) else 0

    def _write(self, address: int, value: int) -> None:
        check_address(address, "Subleq")
        if address >= len(self.cells):
            self.cells.extend([0] * (address + 1 - len(self.cells)))
        self.cells[address] = value

    def step(self) -> None:
        if self.halted:
            return
        if self.pc + 2 >= len(self.cells):
            raise HaltError(
                "incomplete Subleq instruction",
                hint="provide all three addresses for the fetched Subleq instruction",
            )
        a, b, c = self.cells[self.pc : self.pc + 3]
        if a == -1:  # input a byte into b
            if b < 0:
                raise syntax_error(
                    "Subleq input requires a nonnegative destination",
                    (
                        "use -1 as the input operand and a valid nonnegative "
                        "destination address"
                    ),
                )
            check_address(b, "Subleq")
            byte = self.io.input_char() % 256  # EOF raises with pc unmoved
            self.pc += 3
            self._write(b, byte)
        elif b == -1:  # output the byte at a
            self.io.print_char(chr(self._read(a) % 256))
            self.pc += 3
        else:  # mem[b] -= mem[a]; jump to c if the result is not positive
            subtrahend = self._read(a)
            self.pc, result = _advance(self.pc, c, self._read(b), subtrahend)
            self._write(b, result)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse once; every invocation copies the immutable initial memory image."""
    if not isinstance(source, str):
        raise TypeError("subleq machines require text source")
    if options:
        raise TypeError("subleq machines accept no runtime options")

    image = tuple(parse_int_memory(source))

    def build(io: IO) -> _Machine:
        return _Machine(image, io)

    def execute(io: IO) -> CompletionReport:
        return drive(build(io), policy=CAPABILITIES.completion)

    return RuntimePlan(build, execute)


def _execute(code: str, io: IO) -> CompletionReport:
    """Run Subleq with direct jumps and byte I/O."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run Subleq with direct jumps and byte I/O."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
