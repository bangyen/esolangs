"""Interpreter for Blindfolded Arithmetic.

ais523's 2018 language: six unbounded integer registers ``a b c d e i`` and
a list of instructions ``v0 = v1 op v2``, run cyclically with no flow
control.  ``i`` starts as the input and the others as 0.  The first division
by zero is not executed; the run halts and prints ``i`` as it stood.

Instructions are separated by newlines or ``;``, mixed freely; horizontal
whitespace may sit around any token, and blank lines are allowed.

Commands:
    ``+`` ``-`` ``*``: integer arithmetic.
    ``/``: division truncated toward zero; a zero divisor halts.

Input/output:
    One positive decimal integer, read before the first instruction; reading
    at EOF raises.  The output is ``i`` in decimal, with no newline.

Errors:
    ProgramError: A statement that is not ``v0 = v1 op v2`` over the six
    register names, and a program with no instruction.
    InputExhaustedError: No input integer.
    ArgumentError: An input token that is not an integer, or one that is not
    positive.

Decisions:
    * A program with no instruction is malformed: "executes the list of
      instructions cyclically" defines no step for an empty list.
    * Input and output are decimal text; the spec names the values, not
      their framing.
"""

import re

from esolangs.exceptions import ArgumentError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import trunc_div
from esolangs.runtime.source_hints import syntax_error

#: The register names, in the order of :attr:`_Machine.memory`.
REGISTERS = "abcdei"
_STATEMENT = re.compile(
    r"[ \t]*([a-ei])[ \t]*=[ \t]*([a-ei])[ \t]*([-+*/])[ \t]*([a-ei])[ \t]*"
)
_EMPTY = "a Blindfolded Arithmetic program needs at least one instruction"
#: Destination, operator, and the two source registers, as indices.
type _Instruction = tuple[int, str, int, int]
#: The register values, and the next instruction's index.
type _State = tuple[tuple[int, ...], int]


def _parse(code: str) -> tuple[tuple[_Instruction, ...], tuple[int, ...]]:
    """Return the instructions and each one's source offset."""
    program = []
    offsets = []
    for found in re.finditer(r"[^;\n]+", code):
        text = found.group()
        if not text.strip(" \t"):
            continue
        parsed = _STATEMENT.fullmatch(text)
        if parsed is None:
            raise syntax_error(
                f"{text.strip()!r} is not a Blindfolded Arithmetic instruction",
                "write v0 = v1 op v2 with registers a-e or i and op one of + - * /",
            )
        v0, v1, op, v2 = parsed.groups()
        program.append(
            (REGISTERS.index(v0), op, REGISTERS.index(v1), REGISTERS.index(v2))
        )
        offsets.append(found.start() + len(text) - len(text.lstrip(" \t")))
    if not program:
        raise syntax_error(
            _EMPTY, "write at least one instruction, for example i = i / a"
        )
    return tuple(program), tuple(offsets)


def _advance(state: _State, instruction: _Instruction, count: int) -> _State | None:
    """Return the state after ``instruction``, or ``None`` when it halts."""
    registers, ind = state
    target, op, left, right = instruction
    x, y = registers[left], registers[right]
    if op == "+":
        value = x + y
    elif op == "-":
        value = x - y
    elif op == "*":
        value = x * y
    elif y == 0:
        return None
    else:
        value = trunc_div(x, y)
    changed = (*registers[:target], value, *registers[target + 1 :])
    return changed, (ind + 1) % count


class _Machine:
    """The six registers, the instruction cursor, and whether ``i`` is printed."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.program, self.offsets = _parse(code)
        value = io.input_num()
        if value <= 0:
            raise syntax_error(
                f"Blindfolded Arithmetic input must be positive, got {value}",
                "supply a positive decimal integer, for example 1",
                error_type=ArgumentError,
            )
        self.state: _State = ((0, 0, 0, 0, 0, value), 0)
        self.halted = False

    @property
    def memory(self) -> list[int]:
        """The registers ``a b c d e i``."""
        return list(self.state[0])

    @property
    def ip(self) -> int:
        """The source offset of the next instruction."""
        return self.offsets[self.state[1]]

    def snapshot(self) -> tuple[object, ...]:
        return (self.state, self.halted, self.io.progress())

    def step(self) -> None:
        if self.halted:
            return
        state = _advance(self.state, self.program[self.state[1]], len(self.program))
        if state is None:
            self.halted = True
            self.io.print_num(self.state[0][-1])
        else:
            self.state = state


def run(code: str, io: IO) -> None:
    """Run a Blindfolded Arithmetic program on the integer read from ``io``."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
