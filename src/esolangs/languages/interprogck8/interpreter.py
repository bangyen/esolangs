"""Interpreter for Interprogck8.

One accumulator (0-255, wrapping) and one *current function* slot.  A
program is one command per line: ``@nd``/``@nt``/``@id``/``@dd`` add or
subtract 1 and 10, ``NnNn``/``nNnN``/``Empty_`` load 0/65/32, ``div``
prints the accumulator as a character, ``u`` reads one, ``$py``/``$ay``
read and write *dice literals*, ``<``..``>`` fills the function slot,
``EXE``/``IFT``/``IFQ`` call it, ``{values/=a/=b/=c}`` sets 84 (``T``) if
at least two of its three arguments differ and 81 (``Q``) otherwise, and
``DownAccLines`` skips the instruction pointer down *accumulator* lines.

Dice literals count *pips*, not characters: ``.`` is 1, ``:`` is 2, ``:.``
is 3, so a literal is ``2*colons + dots``.  The wiki's truth-machine writes
49 colons where its own rule needs 24 colons and a dot, making the literal
98 and both branches print ``T``; the prose and the dice-roll example
(``[. :::]``, a genuine 1-6 roll) outvote it, and ``$ay`` needs a canonical
encoding that character counting cannot supply.  ``tests`` pins both the
verbatim example and the pip-corrected one.

Input/output:
    ``u`` and ``$py`` read one input line each.  ``$ay`` of 0 prints the empty
    string: no dice literal has zero pips.

Errors:
    InputExhaustedError: reading past the end of the input (the repo-wide
    convention).
    HaltError: ``u`` on an empty input line (the spec's EmptyInputError);
    ``$py`` fed anything but a dice literal; ``DownAccLines`` landing past the
    last line (the spec's EOFError); ``<`` with no ``>`` after it, or reached
    while the slot is executing; ``EXE``/``IFT``/``IFQ`` with an empty slot; a
    blank or unrecognised line when executed; a ``z`` on the first line or
    inside the slot.

Decisions:
    * ``{values...}``'s "at least 2 are different" means "not all equal": the
      truth-machine compares the input with itself twice and a literal, so a
      reading needing three distinct values could never fire its ``IFQ``.
    * ``DownAccLines`` lands on ``ip + 1 + acc``, so an accumulator of 0 is a
      plain fall-through.
    * ``<`` encountered in ordinary execution *captures* the lines up to its
      ``>`` into the slot and jumps past them; the wiki's cat example only
      echoes rather than running its body twice under that reading.  The
      wiki forbids nesting.
    * A blank or unrecognised line raises when *executed* rather than at
      parse time -- ``DownAccLines`` and ``z`` make lines legally
      unreachable, so rejecting them upfront would refuse working programs.
      An empty program has no line to run and halts at once.
    * ``z`` deletes itself and the line before it and restarts with the
      accumulator cleared and the slot dropped ("restarts the
      interpretation").  Each ``z`` shortens the program by two lines, so
      restarts are bounded.  Inside the slot it has no unambiguous "previous
      line".
    * ``[a b]`` and ``~`` draw through :mod:`esolangs.runtime.randomness`, so
      a caller can pin them; ``developer`` prints a fixed string rather than
      this file.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Randomness, draw

_TRUE, _FALSE = 84, 81  # ASCII "T" and "Q", what ``{values...}`` stores

#: Fixed ``developer`` output.  The spec calls it implementation-dependent;
#: printing this module's own text would make every run depend on the file
#: on disk, which no test could pin.
_DEVELOPER = "Interprogck8\n"

#: The nullary commands, mapping a line to what it does to the accumulator.
#: ``mathroundtofloor`` floors an integer plus 0.5, which is the integer.
_ARITH: dict[str, int] = {"@nd": 1, "@nt": -1, "@id": 10, "@dd": -10}
_LOAD: dict[str, int] = {"NnNn": 0, "nNnN": 65, "Empty_": 32}
_NOPS = frozenset({"X", "x", "mathroundtofloor"})


def _pips(literal: str) -> int:
    """Return a dice literal's value, or raise on a non-literal."""
    if not literal or any(c not in ":." for c in literal):
        raise HaltError(f"not a dice literal: {literal!r}")
    return 2 * literal.count(":") + literal.count(".")


def _dice(value: int) -> str:
    """Return the canonical dice literal for ``value``: colons, then a dot."""
    return ":" * (value // 2) + "." * (value % 2)


@dataclass(frozen=True)
class _State:
    """One instant of a run.

    ``lines`` is state, not a constant: ``z`` rewrites the program.
    ``slot`` is the current function's captured body, and ``frames`` the
    call stack as ``(body, index)`` pairs -- all hashable, so a whole
    state can go into a set to prove a loop.
    """

    lines: tuple[str, ...]
    ip: int = 0
    acc: int = 0
    slot: tuple[str, ...] | None = None
    frames: tuple[tuple[tuple[str, ...], int], ...] = ()

    @property
    def halted(self) -> bool:
        return not self.frames and self.ip >= len(self.lines)

    @property
    def current(self) -> str:
        """The line about to run: the innermost frame's, or the program's."""
        if self.frames:
            body, index = self.frames[-1]
            return body[index]
        return self.lines[self.ip]


# Calls are frames on an explicit stack, popped as soon as they are
# exhausted, so the cat example's trailing ``EXE`` recurses at constant depth
# and its state repeats: the cycle detector can prove the truth-machine's
# ``1`` branch loops.
def _advance_cursor(state: _State) -> _State:
    """Move past the line just executed, popping every finished frame.

    Popping eagerly keeps a tail-recursive function at constant stack
    depth; otherwise no state repeats and a loop cannot be proved.
    """
    if state.frames:
        body, index = state.frames[-1]
        frames = (*state.frames[:-1], (body, index + 1))
        while frames and frames[-1][1] >= len(frames[-1][0]):
            frames = frames[:-1]
        return replace(state, frames=frames)
    return replace(state, ip=state.ip + 1)


def _call(state: _State) -> _State:
    """Enter the current function, after advancing past the calling line."""
    if state.slot is None:
        raise HaltError("no current function to execute")
    state = _advance_cursor(state)
    if not state.slot:  # an empty body is a call that returns at once
        return state
    return replace(state, frames=(*state.frames, (state.slot, 0)))


def _capture(state: _State) -> _State:
    """Fill the function slot from the ``<`` at the cursor and jump past it."""
    if state.frames:
        raise HaltError("functions cannot be created inside other functions")
    end = state.ip + 1
    while end < len(state.lines) and state.lines[end] != ">":
        if state.lines[end] == "<":
            raise HaltError("nested function opener")
        end += 1
    if end >= len(state.lines):
        raise HaltError("unclosed function")
    body = state.lines[state.ip + 1 : end]
    return replace(state, slot=body, ip=end + 1)


def _restart(state: _State) -> _State:
    """Apply ``z``: drop it and the line before it, then start over."""
    if state.frames:
        raise HaltError("z has no unambiguous previous line inside a function")
    if state.ip == 0:
        raise HaltError("FirstLineError: z on the first line")
    lines = state.lines[: state.ip - 1] + state.lines[state.ip + 1 :]
    return _State(lines)


def _split_args(line: str) -> list[str] | None:
    """Return the three arguments of a ``{values/=a/=b/=c}`` line, else ``None``.

    The caller turns a miss into the unknown-line ``HaltError``.
    """
    if not (line.startswith("{values/=") and line.endswith("}")):
        return None
    args = line[len("{values") : -1].split("/=")
    if len(args) != 4 or args[0] != "":
        return None
    return args[1:]


def _roll(spec: str, acc: int, rng: Randomness | None, byte: int | None) -> int:
    """Evaluate a ``[a b]`` bracket, which never writes the accumulator.

    An omitted bound is the accumulator; ``$py`` is the byte the shell
    read.  A reversed range is normalised rather than refused -- the spec
    says "between a and b inclusive" and names no order.
    """
    parts = spec[1:-1].split(" ")
    if len(parts) != 2:
        raise HaltError(f"malformed random range: {spec!r}")
    bounds = []
    for part in parts:
        if part == "":
            bounds.append(acc)
        elif part == "$py":
            if byte is None:
                raise HaltError("$py inside a range read nothing")
            bounds.append(byte)
        else:
            bounds.append(_pips(part))
    low, high = min(bounds), max(bounds)
    return low + draw(rng, high - low + 1)


def _value(arg: str, acc: int, rng: Randomness | None, byte: int | None) -> int:
    """Evaluate one ``{values...}`` argument without touching the accumulator."""
    if arg == "":
        return acc
    if arg in ("$py", "u"):
        if byte is None:
            raise HaltError(f"{arg} inside a comparison read nothing")
        return byte
    if arg.startswith("[") and arg.endswith("]"):
        return _roll(arg, acc, rng, byte)
    return _pips(arg)


def _read_kinds(line: str) -> tuple[str, ...]:
    """How ``line`` reads input: one ``"pips"``/``"ord"`` per read, in order.

    The kind belongs to the *argument*, not the line: ``{values/=$py/=u/=}``
    parses a dice literal for the first and takes a byte for the second.
    """
    args = _split_args(line)
    if args is None:
        return _arg_kinds(line)
    return tuple(kind for arg in args for kind in _arg_kinds(arg))


def _arg_kinds(arg: str) -> tuple[str, ...]:
    """How one argument reads input; ``()`` for a literal."""
    if arg == "$py":
        return ("pips",)
    if arg == "u":
        return ("ord",)
    if arg.startswith("[") and arg.endswith("]"):
        return tuple("pips" for p in arg[1:-1].split(" ") if p == "$py")
    return ()


def _accumulate(
    line: str, acc: int, rng: Randomness | None, reads: tuple[int, ...]
) -> tuple[int, str | None]:
    """Return a straight-line command's accumulator and printed text."""
    if line in _ARITH:
        return (acc + _ARITH[line]) % 256, None
    if line in _LOAD:
        return _LOAD[line], None
    if line in _NOPS or line == ">":  # a stray closer is a no-op
        return acc, None
    if line == "~":
        return acc, "Interprogck8\n" if draw(rng, 10) == 0 else None
    if line == "developer":
        return acc, _DEVELOPER
    if line == "div":
        return acc, chr(acc)
    if line == "$ay":
        return acc, _dice(acc)
    if line == "Instruction26":
        return acc, chr(acc).join(str(i) for i in range(1, 27))
    if line in ("$py", "u"):
        return reads[0], None
    if line.startswith("[") and line.endswith("]"):
        return _roll(line, acc, rng, reads[0] if reads else None), None
    args = _split_args(line)
    if args is None:
        raise HaltError(f"unknown instruction: {line!r}")
    taken = iter(reads)
    values = [
        _value(a, acc, rng, next(taken, None) if _read_kinds(a) else None) for a in args
    ]
    return (_FALSE if values[0] == values[1] == values[2] else _TRUE), None


def _advance(
    state: _State, rng: Randomness | None = None, reads: tuple[int, ...] = ()
) -> tuple[_State, str | None]:
    """Return the state after one line, and the text to print.

    Pure: input arrives as ``reads`` -- the bytes the shell took for this
    line, in written order -- and output leaves as the returned string.
    """
    line, acc = state.current, state.acc
    if line == "DownAccLines":
        if state.frames:
            # The pointer inside a function body is a frame index, not a
            # program line, so "skip down N lines" names nothing.
            raise HaltError("DownAccLines inside a function body")
        nxt = state.ip + 1 + acc
        if nxt > len(state.lines):
            raise HaltError("EOFError: not enough lines to skip down")
        return replace(state, ip=nxt), None
    if line == "<":
        return _capture(state), None
    if line == "EXE" or (line, acc) in (("IFT", _TRUE), ("IFQ", _FALSE)):
        return _call(state), None
    if line in ("IFT", "IFQ"):
        return _advance_cursor(state), None
    if line == "z":
        return _restart(state), None
    acc, out = _accumulate(line, acc, rng, reads)
    return _advance_cursor(replace(state, acc=acc)), out


#: A ``_State`` flattened for the branching search: the same five fields,
#: without the output the search deliberately drops.
type _BranchState = tuple[
    tuple[str, ...],
    int,
    int,
    tuple[str, ...] | None,
    tuple[tuple[tuple[str, ...], int], ...],
]


class _Pinned:
    """A :class:`Randomness` answering every draw with one fixed value.

    The branching search enumerates outcomes by running the transition once
    per pinned draw, so a line makes exactly the choice being quantified.
    """

    def __init__(self, value: int) -> None:
        self._value = value

    def randbelow(self, upper: int) -> int:
        return self._value % upper


def _branch_state(state: object) -> _State:
    """Rebuild a ``_State`` from a branching-search tuple."""
    return _State(*cast("_BranchState", state))


def _draw_range(line: str) -> int:
    """How many distinct outcomes ``line`` has: 1 unless it draws.

    ``~`` has ten (it prints on one of them).  ``[a b]`` spans at most the
    accumulator's 256 values, which is the widest a bound can be.
    """
    if line == "~":
        return 10
    return 256 if line.startswith("[") and line.endswith("]") else 1


def _outcomes(state: _State) -> tuple[_State, ...]:
    """Every state one line could reach, one per draw it could make."""
    seen: dict[_State, None] = {}
    for draw_value in range(_draw_range(state.current)):
        nxt, _out = _advance(state, _Pinned(draw_value))
        seen.setdefault(nxt, None)
    return tuple(seen)


class _Machine:
    """The run state: the program lines, accumulator, slot, and call stack."""

    #: ``ip`` starts with a line number, with each open frame's index after it.
    ip_shape = "line"

    def __init__(
        self, code: str | list[str], io: IO, rng: Randomness | None = None
    ) -> None:
        lines = code.splitlines() if isinstance(code, str) else list(code)
        self.state = _State(tuple(lines))
        self.io = io
        self.rng = rng

    @property
    def halted(self) -> bool:
        return self.state.halted

    @property
    def ip(self) -> tuple[int, ...]:
        """The instruction position: the line, plus each open frame's index."""
        return (self.state.ip, *(index for _body, index in self.state.frames))

    @property
    def memory(self) -> list[int]:
        """The one addressable cell."""
        return [self.state.acc]

    @property
    def stack(self) -> list[object]:
        """The call stack, one entry per open ``EXE``."""
        return [index for _body, index in self.state.frames]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete state, hashable, with the input cursor."""
        s = self.state
        return (s.lines, s.ip, s.acc, s.slot, s.frames, self.io.progress())

    # The branching-search protocol.  ``[a b]`` and ``~`` are the two random
    # instructions, so a hang proof has to hold over *every* draw.  A line
    # that reads input declines instead of forking: sibling branches cannot
    # share one input cursor.

    def branching_snapshot(self) -> tuple[object, ...]:
        """Return the state a search starts from, output deliberately absent."""
        s = self.state
        return (s.lines, s.ip, s.acc, s.slot, s.frames)

    def branching_halted(self, state: object) -> bool:
        """Report whether a search state has run off the program."""
        return _branch_state(state).halted

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[tuple[object, ...], ...] | None:
        """Every state this line could reach, over all draws it could make.

        ``None`` where the line reads input: the siblings would have to
        share one cursor, so the search declines rather than guessing.
        """
        current = _branch_state(state)
        if _read_kinds(current.current):
            return None
        try:
            reached = _outcomes(current)
        except HaltError:
            # A line the run cannot execute ends this branch rather than
            # ending the search: an unreachable neighbour is not a hang.
            return ()
        return tuple(
            (nxt.lines, nxt.ip, nxt.acc, nxt.slot, nxt.frames) for nxt in reached
        )

    def step(self) -> None:
        """Execute one line; the two ports live here and nowhere else."""
        if self.halted:
            return
        reads = []
        for kind in _read_kinds(self.state.current):
            # ``u``'s EmptyInputError is the spec's, so an empty line is an
            # error here rather than the repo's usual read-as-0; running out
            # of input is the different case and still raises EOFError.
            val = self.io.input_str()
            if not val:
                raise HaltError("EmptyInputError: empty input")
            reads.append(_pips(val) if kind == "pips" else ord(val[0]))
        self.state, out = _advance(self.state, self.rng, tuple(reads))
        if out:
            self.io.print_str(out)


def run(code: str | list[str], io: IO, rng: Randomness | None = None) -> None:
    """Run ``code`` to its halt; ``rng`` pins ``[a b]`` and ``~``."""
    drive(_Machine(code, io, rng))


if __name__ == "__main__":
    script_main(run)
