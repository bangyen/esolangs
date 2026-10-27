"""Interpreter for BASICER.

A program is one instruction per line, every line numbered or none.  Lines
run in ascending number order (source order when unnumbered, numbered
1, 2, ... from the top); running off the last line halts.

Commands:
    ``CLEAR``              clear the console and screen
    ``PLOT X Y #RRGGBB``   colour a pixel, X and Y in 0-99
    ``PRINT text``         print the rest of the line and a newline
    ``PAUSE``              wait for a button
    ``GOTO a``             jump to line ``a``
    ``GOTO a b ...``       read a choice ``k`` and jump to the ``k``-th line

Input/output:
    A menu ``GOTO`` reads one input line holding its choice, an integer;
    ``PRINT`` writes one line.

Errors:
    ProgramError: an unknown instruction, malformed operands, a duplicate
    line number, or numbers on only some lines.
    InputExhaustedError: a menu ``GOTO`` at EOF.
    ArgumentError: a menu choice that is not an integer.
    HaltError: a menu choice outside 1 to the number of targets.

Decisions:
    * A jump to a line that does not exist halts, as the page says, without
      an error; the adder example exits this way (``3`` picks line 200).
    * ``CLEAR`` and ``PLOT`` touch the screen only; output is a terminal
      stream, so printed text is not erased.  ``PLOT`` still validates.
    * ``PAUSE`` reads nothing: the examples' menus would otherwise lose a
      choice to each pause.
    * Unnumbered lines are addressed by their 1-based position; the page
      allows omitting numbers but gives no other target for ``GOTO``.
    * Blank lines are skipped, neither counted nor numbered.
    * The page names one choice per prompt and no reprompt, so a choice
      out of range halts with an error rather than asking again.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

_PLOT = re.compile(r"(\d{1,2}) (\d{1,2}) #[0-9A-Fa-f]{6}")


class _Line(NamedTuple):
    """One parsed instruction: its keyword and, for ``GOTO``, its targets."""

    op: str
    text: str
    targets: tuple[int, ...]


def _instruction(body: str) -> _Line:
    """Parse one instruction, rejecting an unknown or malformed one."""
    op, _, rest = body.partition(" ")
    if op in ("CLEAR", "PAUSE") and not rest:
        return _Line(op, "", ())
    if op == "PRINT":
        return _Line(op, rest, ())
    if op == "PLOT" and _PLOT.fullmatch(rest):
        return _Line(op, rest, ())
    if op == "GOTO" and rest and all(t.isdigit() for t in rest.split()):
        return _Line(op, "", tuple(int(t) for t in rest.split()))
    raise syntax_error(
        f"cannot parse {body!r}",
        "use CLEAR, PLOT X Y #RRGGBB, PRINT text, PAUSE or GOTO numbers",
    )


def _parse(code: str) -> tuple[tuple[_Line, ...], dict[int, int]]:
    """Return the lines in run order and a map from line number to index."""
    rows = [row.strip() for row in code.split("\n") if row.strip()]
    numbered = [row.split(" ", 1)[0].isdigit() for row in rows]
    if any(numbered) and not all(numbered):
        raise syntax_error(
            "line numbers on only some lines", "number every line or none"
        )
    if not any(numbered):
        lines = tuple(_instruction(row) for row in rows)
        return lines, {num: num - 1 for num in range(1, len(lines) + 1)}
    pairs = sorted(
        (int(num), body) for num, _, body in (r.partition(" ") for r in rows)
    )
    nums = [num for num, _ in pairs]
    if len(set(nums)) < len(nums):
        raise syntax_error("a duplicate line number", "give every line its own number")
    return tuple(_instruction(body) for _, body in pairs), {
        num: ind for ind, num in enumerate(nums)
    }


def _advance(
    ind: int, lines: tuple[_Line, ...], index: dict[int, int], choice: int | None = None
) -> tuple[int, str | None]:
    """Return the next line index and any printed line; pure.

    A jump to a missing line lands past the end, which halts.
    """
    line = lines[ind]
    if line.op == "PRINT":
        return ind + 1, line.text + "\n"
    if line.op == "GOTO":
        target = line.targets[0 if choice is None else choice - 1]
        return index.get(target, len(lines)), None
    return ind + 1, None


class _Machine:
    """A BASICER run: the index of the line about to run."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.lines, self.index = _parse(code)
        self.io = io
        self.ind = 0

    @property
    def halted(self) -> bool:
        return self.ind >= len(self.lines)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.io.progress())

    def step(self) -> None:
        """Run one line; a menu's choice is read here."""
        if self.halted:
            return
        line = self.lines[self.ind]
        choice = None
        if line.op == "GOTO" and len(line.targets) > 1:
            raw = self.io.input_str().strip()
            if not raw.lstrip("-").isdigit():
                raise ArgumentError(f"menu choice {raw!r} is not an integer")
            choice = int(raw)
            if not 1 <= choice <= len(line.targets):
                raise HaltError(
                    f"choice {choice} outside 1 to {len(line.targets)}",
                    hint="answer a menu with one of its numbered choices",
                )
        self.ind, out = _advance(self.ind, self.lines, self.index, choice)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a BASICER program until it leaves its last line."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
