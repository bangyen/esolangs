r"""Interpreter for Codesick.

Memory maps every string to a string, each initially to itself; ``*X``
is the string ``X`` maps to.  The only instruction, ``S codesick A B C D
E;``, sets ``*A`` to ``*A + *B``, then ``*C`` to ``**C``, then, if
``*D`` occurs in ``*A``, deletes its first occurrence and jumps to the
instruction labelled ``D``, else jumps to the one labelled ``E``.  A
jump to a missing label halts.  Execution starts at the first
instruction.  An argument is ``"..."`` (``\"`` is a quote) or a bare
run without whitespace, ``;`` or ``"``; bare ``codesick``, ``in`` and
``out`` are keywords.  The wiki's Hello world, Cat, XKCD and
Truth-machine run as stated.

Input/output:
    Every ``in`` is replaced by the input before the run, so an empty
    stdin is an empty string, never EOF; an ``out`` A prints ``B`` instead
    of appending and fails the test.

Errors:
    ProgramError: A bare ``out`` other than as A; a bare ``codesick`` other
        than as the keyword; a wrong argument count; a duplicate label; an
        unterminated string; a missing ``;``.

Decisions:
    * A jump goes to the label ``D`` or ``E`` as written, though the wiki's
      prose says ``*D``/``*E``: ``1 codesick out 1 * 1;`` must loop.
      Forced, like the next, by the wiki's truth machine, whose first
      instruction sets ``*0`` to ``a`` on ``0`` and ``*1`` to ``1a`` on ``1``.
    * ``out`` prints ``B`` as written (the prose's word), not ``*B``: the
      truth machine's lines must print ``0`` and ``1``.
    * With four arguments after ``codesick`` the omitted one is C (the wiki
      makes only the dereference optional), which dereferences ``""``.
    * ``in`` is all of stdin, read once; every ``in`` gets the same string.
    * Instructions without a label are reachable only as the first one, so
      the wiki's removal of them is unobservable and not modelled.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

_TOKEN = re.compile(r'"((?:\\"|[^"])*)"|([^\s;"]+)|(;)|(\S)')
_KEYWORDS = frozenset({"codesick", "in", "out"})

#: A parsed argument: a string, or a bare keyword as a 1-tuple.
type _Arg = str | tuple[str]
#: ``(offset, label, A, B, C, D, E)`` before ``in`` is replaced.
type _Parsed = tuple[int, _Arg | None, _Arg, _Arg, _Arg, _Arg, _Arg]
#: ``(label, A, B, C, D, E)``; ``A`` is ``None`` for ``out``.
type _Instruction = tuple[str | None, str | None, str, str, str, str]


def _load(code: str) -> tuple[list[_Parsed], bool]:
    """Return the instructions with ``in`` unreplaced, and whether one reads."""
    program: list[_Parsed] = []
    labels: set[str] = set()
    args: list[_Arg] = []
    start = 0
    for match in _TOKEN.finditer(code):
        quoted, bare, end, stray = match.groups()
        if stray is not None:
            raise ValueError(f"Codesick: unterminated string at {match.start()}")
        if not args:
            start = match.start()
        if end is None:
            if quoted is not None:
                args.append(quoted.replace('\\"', '"'))
            else:
                args.append((bare,) if bare in _KEYWORDS else bare)
            continue
        keyword = [k for k, arg in enumerate(args) if arg == ("codesick",)]
        if keyword not in ([0], [1]) or len(args) - keyword[0] not in (5, 6):
            raise ValueError(f"Codesick: malformed instruction at {start}")
        label = args[0] if keyword == [1] else None
        operands = args[keyword[0] + 1 :]
        if len(operands) == 4:
            operands.insert(2, "")
        if ("out",) in [label, *operands[1:]]:
            raise ValueError(f"Codesick: 'out' outside A at {start}")
        if isinstance(label, str):
            if label in labels:
                raise ValueError(f"Codesick: duplicate label {label!r}")
            labels.add(label)
        program.append((start, label, *operands))  # type: ignore[arg-type]
        args = []
    if args:
        raise ValueError("Codesick: the last instruction has no ';'")
    reads = any(("in",) in parsed[1:] for parsed in program)
    return program, reads


def _resolve(parsed: _Parsed, given: str) -> _Instruction:
    """Replace ``in`` with the input; ``out`` as A becomes ``None``."""
    label, a, b, c, d, e = (given if arg == ("in",) else arg for arg in parsed[1:])
    assert all(isinstance(arg, str) for arg in (b, c, d, e))
    return (
        label if isinstance(label, str) else None,
        a if isinstance(a, str) else None,
        str(b),
        str(c),
        str(d),
        str(e),
    )


def _advance(
    instruction: _Instruction, memory: Mapping[str, str]
) -> tuple[tuple[tuple[str, str], ...], str | None, str]:
    """Run one instruction: the strings it rewrote, any output, the jump label.

    Pure: ``memory`` holds the strings not mapping to themselves and is
    only read.
    """
    _, a, b, c, d, e = instruction
    written: dict[str, str] = {}

    def star(name: str) -> str:
        return written.get(name, memory.get(name, name))

    out = None
    if a is None:
        out = b
    else:
        written[a] = star(a) + star(b)
    written[c] = star(star(c))
    label = e
    if a is not None and star(d) in star(a):
        written[a] = star(a).replace(star(d), "", 1)
        label = d
    return tuple(written.items()), out, label


class _Machine:
    """The shell around :func:`_advance`: memory, labels, input and output."""

    #: Stdin is one string, read once: an underfed run reads a shorter
    #: string and answers the row it spells.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        parsed, reads = _load(code)
        given = io.input_all() if reads else ""
        self.program = [_resolve(p, given) for p in parsed]
        self.offsets = [p[0] for p in parsed]
        self.labels = {
            ins[0]: k for k, ins in enumerate(self.program) if ins[0] is not None
        }
        self.end = len(code)
        #: Only the strings that no longer map to themselves.
        self.memory: dict[str, str] = {}
        self.pc: int | None = 0 if self.program else None

    @property
    def halted(self) -> bool:
        return self.pc is None

    @property
    def ip(self) -> int:
        """The current instruction's source offset; the code's length once halted."""
        return self.end if self.pc is None else self.offsets[self.pc]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.pc, frozenset(self.memory.items()), self.io.progress())

    def step(self) -> None:
        """Run one instruction."""
        if self.pc is None:
            return
        written, out, label = _advance(self.program[self.pc], self.memory)
        for name, value in written:
            if value == name:
                self.memory.pop(name, None)
            else:
                self.memory[name] = value
        if out is not None:
            self.io.print_str(out)
        self.pc = self.labels.get(label)


def run(code: str, io: IO) -> None:
    """Run a Codesick program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
