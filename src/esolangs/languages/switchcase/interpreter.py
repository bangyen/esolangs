"""Interpreter for SwitchCase.

None1's 2024 language of unbounded integer variables, whose only control
flow is the switch-case.  A program is a sequence of switch cases, each a
``$name`` line, then ``integer?commands`` arms with distinct integers, then
at most one ``!commands`` default.  A case runs the arm whose integer equals
the named variable, else the default, else nothing, and control passes to
the next case; the program halts past the last one.  At the start the only
variable is ``_``, zero.

Commands:
    ``+n`` / ``-n`` add / subtract ``n`` from the case's variable.
    ``,`` reads a character into it as its code; ``#`` reads an integer.
    ``.`` prints it as a character; ``@`` prints it as an integer.
    ``'k`` jumps to the ``k``-th case, counting from 1.
    ``=name`` defines the variable ``name`` as zero.

Input/output:
    ``,`` reads one character; ``#`` reads a whitespace-delimited signed
    decimal integer; either at EOF raises.  ``.`` and ``@`` print with no
    separator.

Errors:
    ProgramError: a line outside the case syntax, an arm before any
    ``$`` line, a case with no arm, a repeated integer in one case, a second
    default, and an unknown command.
    InputExhaustedError: ``,`` or ``#`` with no input left.
    ArgumentError: ``#`` given a token that is not an integer.
    HaltError: a case on an undefined variable, a jump to no case, and
    ``.`` on a value that is no character.

Decisions:
    * A jump takes effect at once: the rest of its arm does not run.  The
      page never puts a command after one.
    * A default runs a command sequence, as an arm does; the page writes
      ``!<command>`` but its arms show sequences.
    * A name is a letter or ``_``, then letters, digits and ``_``; ``=A=B``
      defines two variables, as the Minsky translation does.
    * ``=name`` on a defined variable sets it back to zero.
    * Blank lines and surrounding whitespace on a line are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: ``(op, argument)``: op one of ``+ - , # . @ ' =``.
type _Command = tuple[str, int | str]
#: The variables, sorted by name: a value, so a step returns a new one.
type _Env = tuple[tuple[str, int], ...]
#: ``(case, arm, at, env)``: ``arm`` is ``None`` before the case selects
#: one, else the selected command list's key (an integer, or ``"!"`` for
#: the default); ``at`` indexes its commands.
type _State = tuple[int, int | str | None, int, _Env]

_COMMAND = re.compile(r"([+-])(\d+)|([,#.@])|'(\d+)|=([A-Za-z_][A-Za-z0-9_]*)")
_ARM = re.compile(r"(-?\d+)\?(.*)", re.S)


@dataclass(frozen=True, slots=True)
class _Case:
    variable: str
    arms: dict[int | str, tuple[_Command, ...]]


def _commands(text: str, line: str) -> tuple[_Command, ...]:
    out: list[_Command] = []
    at = 0
    while at < len(text):
        match = _COMMAND.match(text, at)
        if match is None:
            raise syntax_error(
                f"unknown SwitchCase command at {text[at:]!r} in {line!r}",
                "use +n -n , # . @ 'k =name",
            )
        sign, amount, io_op, target, name = match.groups()
        if sign:
            out.append((sign, int(amount)))
        elif io_op:
            out.append((io_op, 0))
        elif target:
            out.append(("'", int(target)))
        else:
            out.append(("=", name))
        at = match.end()
    return tuple(out)


def _parse(code: str) -> tuple[_Case, ...]:
    cases: list[_Case] = []
    for raw in code.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("$"):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", line[1:]):
                raise syntax_error(
                    f"a SwitchCase case needs a variable name: {line!r}",
                    "write $name, for example $_",
                )
            cases.append(_Case(line[1:], {}))
            continue
        if not cases:
            raise syntax_error(
                f"a SwitchCase arm comes before any case: {line!r}",
                "start a case with $name first",
            )
        arms = cases[-1].arms
        if line.startswith("!"):
            if "!" in arms:
                raise syntax_error(
                    f"a SwitchCase case has a second default: {line!r}",
                    "keep one ! line a case",
                )
            arms["!"] = _commands(line[1:], line)
            continue
        match = _ARM.fullmatch(line)
        if match is None:
            raise syntax_error(
                f"not a SwitchCase arm: {line!r}", "write integer?commands"
            )
        key = int(match.group(1))
        if key in arms:
            raise syntax_error(
                f"SwitchCase integer {key} is repeated in one case",
                "give each arm of a case its own integer",
            )
        arms[key] = _commands(match.group(2), line)
    for case in cases:
        if not any(key != "!" for key in case.arms):
            raise syntax_error(
                f"the SwitchCase case on {case.variable} has no arm",
                "a case needs at least one integer?commands line",
            )
    return tuple(cases)


def _get(env: _Env, name: str) -> int:
    for key, value in env:
        if key == name:
            return value
    raise HaltError(f"SwitchCase variable {name} is not defined")


def _set(env: _Env, name: str, value: int) -> _Env:
    return tuple(sorted({**dict(env), name: value}.items()))


def _advance(
    state: _State, cases: tuple[_Case, ...], value: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one selection or command, and the text to print.

    Pure: a read arrives as ``value``, a write leaves as the return value.
    """
    case_at, arm, at, env = state
    case = cases[case_at]
    if arm is None:
        current = _get(env, case.variable)
        key: int | str | None = (
            current if current in case.arms else "!" if "!" in case.arms else None
        )
        if key is None:
            return (case_at + 1, None, 0, env), None
        return (case_at, key, 0, env), None
    commands = case.arms[arm]
    if at >= len(commands):
        return (case_at + 1, None, 0, env), None
    op, argument = commands[at]
    current = _get(env, case.variable)
    out = None
    if op == "+":
        env = _set(env, case.variable, current + int(argument))
    elif op == "-":
        env = _set(env, case.variable, current - int(argument))
    elif op in ",#":
        assert value is not None
        env = _set(env, case.variable, value)
    elif op == "@":
        out = str(current)
    elif op == ".":
        if not 0 <= current <= 0x10FFFF:
            raise HaltError(f"SwitchCase cannot print {current} as a character")
        out = chr(current)
    elif op == "'":
        target = int(argument)
        if not 1 <= target <= len(cases):
            raise HaltError(f"SwitchCase has no case {target} to jump to")
        return (target - 1, None, 0, env), None
    else:
        env = _set(env, str(argument), 0)
    return (case_at, arm, at + 1, env), out


class _Machine:
    """The cases, the position in them and the variables."""

    #: ``ip`` is the case, the selected arm's command, ``-1`` before one.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.cases = _parse(code)
        self.state: _State = (0, None, 0, (("_", 0),))

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.cases)

    @property
    def ip(self) -> tuple[int, ...]:
        case_at, arm, at, _ = self.state
        return (case_at, -1 if arm is None else at)

    @property
    def memory(self) -> dict[str, int]:
        return dict(self.state[3])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.state, self.io.progress())

    def step(self) -> None:
        if self.halted:
            return
        case_at, arm, at, _ = self.state
        value = None
        if arm is not None:
            commands = self.cases[case_at].arms[arm]
            if at < len(commands):
                op = commands[at][0]
                if op == ",":
                    value = self.io.input_char()
                elif op == "#":
                    value = self.io.input_num()
        self.state, out = _advance(self.state, self.cases, value)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a SwitchCase program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
