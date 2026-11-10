"""Interpreter for lol waht i cant edit talk pages.

One statement per line over named integer variables.  A loop line ends in
``{`` and a line holding only ``}`` closes it; the loop runs its body
while the variable equals the amount.  The run ends at ``waht i got
banned`` or past the last line.

Commands:
    ``user:?``                                  define ``?`` as 0
    ``edit user talk:? to change n messages``   add n to ``?``
    ``edit user talk:? to remove n messages``   subtract n from ``?``
    ``JUST LET ME CHANGE n MESSAGES ON ? {``    loop while ``?`` = n
    ``im awesome tottaly but no ?``             read a number into ``?``
    ``grr why u do this ?``                     print ``?`` as a character
    ``i hate u ?``                              print ``?`` as a number
    ``waht i got banned``                       halt
    ``S --tommyaweosme ...``                    print ``S`` (PSTF's signature)

Input/output:
    The read takes one whitespace-delimited integer; prints add no
    separator.

Errors:
    ProgramError: a line matching no command, or an unmatched brace.
    InputExhaustedError: a read at EOF.
    ArgumentError: a read given a non-integer token.
    HaltError: a variable used before its ``user:`` line, or a character
    print outside Unicode.

Decisions:
    * An amount ``n`` is a decimal literal, ``no`` (0), or a variable: the
      A+B program adds ``用户1`` and the cat loops on ``AUTOCORRECT``
      equal to itself.
    * ``MESSAGE`` and ``MESSAGES`` both parse: the truth machine writes
      ``1 MESSAGE``.
    * Keywords and variable names fold case: the cat defines
      ``autocorrect`` and loops on ``AUTOCORRECT``, and A+B writes
      ``User:``.  ``i hate you`` is ``i hate u``, as the cat spells it.
    * The read is numeric, after the cat's heading "numbers instead of
      ascii characters".
    * The signature print takes everything before `` --tommyaweosme`` and
      ignores the timestamp; it prints no newline.
    * Redefining a variable resets it to 0; blank lines are skipped.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.lol_waht_i_cant_edit_talk_pages.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer, parse_integer
from esolangs.runtime.source_hints import syntax_error

_INTEGER_PATTERN = re.compile("[+-]?[0-9]+")

_NAME = r"(\S+)"
_PATTERNS = (
    ("def", re.compile(r"user:" + _NAME, re.IGNORECASE)),
    (
        "add",
        re.compile(
            r"edit user talk:(\S+) to (change|remove) (\S+) messages?", re.IGNORECASE
        ),
    ),
    (
        "loop",
        re.compile(r"just let me change (\S+) messages? on (\S+) \{", re.IGNORECASE),
    ),
    ("read", re.compile(r"im awesome tottaly but no " + _NAME, re.IGNORECASE)),
    ("chr", re.compile(r"grr why u do this " + _NAME, re.IGNORECASE)),
    ("num", re.compile(r"i hate (?:u|you) " + _NAME, re.IGNORECASE)),
    ("halt", re.compile(r"waht i got banned", re.IGNORECASE)),
    ("end", re.compile(r"\}")),
    ("say", re.compile(r"(.*?) --tommyaweosme\b.*")),
)

#: One parsed line: its kind, its operands, and a jump target for loops.
type _Op = tuple[str, tuple[str, ...], int]


class _State(NamedTuple):
    """The statement cursor and the variables, as a sorted tuple."""

    pc: int
    env: tuple[tuple[str, int], ...]


def _parse(code: str) -> list[_Op]:
    """Return the statements, each loop and ``}`` holding its partner."""
    ops: list[_Op] = []
    opened: list[int] = []
    for line in code.split("\n"):
        text = line.strip()
        if not text:
            continue
        found = [(k, m) for k, p in _PATTERNS if (m := p.fullmatch(text))]
        if not found:
            raise syntax_error(
                f"unknown command {text!r}", "write one of the page's commands"
            )
        kind, match = found[0]
        args = tuple(g.casefold() if kind != "say" else g for g in match.groups())
        if kind == "loop":
            opened.append(len(ops))
        elif kind == "end":
            if not opened:
                raise syntax_error("unmatched '}'", "open the loop with a { line")
            start = opened.pop()
            ops[start] = ("loop", ops[start][1], len(ops) + 1)
            ops.append(("end", (), start))
            continue
        ops.append((kind, args, -1))
    if opened:
        raise syntax_error("unmatched '{'", "close the loop with a } line")
    return ops


def _value(env: dict[str, int], token: str) -> int:
    """Read an amount: a literal, ``no``, or a defined variable."""
    if _INTEGER_PATTERN.fullmatch(token):
        return parse_integer(token)
    if token == "no":
        return 0
    if token not in env:
        raise HaltError(
            f"variable {token!r} is not defined",
            hint=f"define it first with user:{token}",
        )
    return env[token]


def _advance(
    state: _State, ops: Sequence[_Op], number: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one statement, and the text it prints.

    Pure apart from the undefined-variable error; a read arrives as ``number``.
    """
    pc, env_items = state
    env = dict(env_items)
    kind, args, target = ops[pc]
    out = None
    pc += 1
    if kind == "def":
        env[args[0]] = 0
    elif kind == "add":
        amount = _value(env, args[2])
        sign = 1 if args[1] == "change" else -1
        env[args[0]] = _value(env, args[0]) + sign * amount
    elif kind == "loop":
        if _value(env, args[1]) != _value(env, args[0]):
            pc = target
    elif kind == "end":
        pc = target
    elif kind == "read" and number is not None:
        _value(env, args[0])
        env[args[0]] = number
    elif kind == "chr":
        value = _value(env, args[0])
        if not 0 <= value <= 0x10FFFF:
            raise HaltError(
                f"{format_integer(value)} is not a character",
                hint="print values in 0..0x10FFFF",
            )
        out = chr(value)
    elif kind == "num":
        out = format_integer(_value(env, args[0]))
    elif kind == "say":
        out = args[0]
    elif kind == "halt":
        pc = len(ops)
    return _State(pc, tuple(sorted(env.items()))), out


_WORKSPACE_MODEL = WorkspaceModel(
    "lol-waht-i-cant-edit-talk-pages-v1", ("instruction", "variables", "input_cursor")
)


class _Machine:
    """A run: the parsed statements and one immutable ``_State``."""

    # ``ip`` counts parsed statements, not source characters.
    ip_shape = "opaque"

    def __init__(self, code: str | tuple[_Op, ...], io: IO) -> None:
        self.ops = _parse(code) if isinstance(code, str) else code
        self.io = io
        self.state = _State(0, ())

    @property
    def ip(self) -> int:
        return self.state.pc

    @property
    def halted(self) -> bool:
        return self.state.pc >= len(self.ops)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of storage and cycle grouping."""
        return _WORKSPACE_MODEL.capture(
            instruction=self.state.pc,
            variables=frozenset(self.state.env),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Run one statement; the read and the print happen here."""
        if self.halted:
            return
        kind = self.ops[self.state.pc][0]
        number = self.io.input_num() if kind == "read" else None
        self.state, out = _advance(self.state, self.ops, number)
        if out is not None:
            self.io.print_str(out)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain parsed instructions and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("lol_waht_i_cant_edit_talk_pages machines require text source")
    if options:
        raise TypeError(
            "lol_waht_i_cant_edit_talk_pages machines accept no runtime options"
        )

    image = tuple(_parse(source))
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | tuple[_Op, ...], io: IO) -> CompletionReport:
    """Run a program until it is banned or runs out of lines."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a program until it is banned or runs out of lines."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
