"""Interpreter for Nevermind.

Line-based commands: ``print`` joins its arguments and writes them with no
separator or trailing newline (the wiki says only "Outputs *text* to the
screen", and its Hello-World example shows none), ``input`` stores a line in
the answer variable, ``make`` computes arithmetic (``+ - * /`` on numbers,
``++`` concatenating strings), and ``if``/``loop``/``endloop`` branch on
comparisons.  ``$name`` references a variable.

The wiki never states operand types: its only arithmetic example is a
calculator whose operands come from ``input``, so any of them can be
text.  Since the language has ``++`` for joining strings, ``+ - * /`` and
the ordered comparisons ``<``/``>`` are read as numeric, and a string
reaching one of them halts with :class:`~esolangs.exceptions.HaltError`
rather than falling through to Python's meaning for it (which would
concatenate, repeat, or order the operands instead).  ``=`` is not an
ordering, so it still compares strings.

A number is written in ASCII, either as digits or as digits around a
single ``.``; a decimal is only read as one when the spelling matches how
it prints back, so ``02.5`` stays the text the program wrote.

An ``if``/``loop``/``endloop`` with no matching partner, or a command
short of the operands its form requires (``make`` without a value,
``if`` without both sides of its comparison, ``loop`` without a count),
is a structurally malformed program and is rejected with
:class:`ValueError`; dividing by zero,
referencing an undefined ``$name``, or ``input`` with no prompt are invalid
operations that halt the program with :class:`~esolangs.exceptions.HaltError`
(or, for the missing prompt, :class:`ValueError`).

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the parsed program, the
variables, and the loop/skip cursor state), so it is step-capable:
``step()`` executes one line and ``halted`` is true once the cursor
reaches the end of the program.
"""

import sys
from collections.abc import Mapping, Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def find(code: Sequence[Sequence[str | int | float]], ind: int) -> int:
    """Return the index of the matching ``if``/``loop`` partner for ``ind``.

    Raises :class:`ValueError` when the partner is missing: the wiki defines
    ``if``/``endif`` and ``loop``/``endloop`` only for matched pairs, so an
    unmatched marker is a malformed program.
    """
    if "end" in (op := str(code[ind][0])):
        match = op[3:]
        move = -1
    else:
        match = "end" + op
        move = 1

    num = move
    ind += move

    while num:
        if not 0 <= ind < len(code):
            raise ValueError(f"unmatched {op}")
        # A blank line parses to no tokens and ``step`` skips it, so the
        # scan for the partner has to skip it too rather than read a
        # command out of it.
        if line := code[ind]:
            if line[0] == op:
                num += move
            elif line[0] == match:
                num -= move
        ind += move
    return ind - 1


def _as_number(value: str) -> int | float | None:
    """Return ``value`` as a number, or ``None`` if it does not spell one.

    Only ASCII spellings count: :meth:`str.isdigit` is also true for
    superscript and Arabic-Indic digits, which :func:`int` either rejects
    or reads as a value the program never wrote, so those stay strings.
    """
    if not value.isascii():
        return None
    if value.isdigit():
        return int(value)
    whole, dot, frac = value.partition(".")
    if dot and whole.isdigit() and frac.isdigit():
        # Only a spelling that survives the round trip: ``str`` renders a
        # float back without the written leading zeros, so "02.5" would
        # print as "2.5" and silently lose a character the program wrote.
        number = float(value)
        if str(number) == value:
            return number
    return None


def _number(value: str | int | float, op: str) -> int | float:
    """Return ``value`` as a number, halting if it is not one.

    ``+ - * /`` and the ``<``/``>`` comparisons are arithmetic: the wiki
    gives Nevermind ``++`` for joining strings, so a string reaching one of
    the numeric operators has no defined result and the program halts
    rather than falling through to Python's own meaning for it (which would
    concatenate, repeat, or order the operands instead).
    """
    if isinstance(value, str):
        raise HaltError(f"{op} needs a number, got {value!r}")
    return value


#: One instant of a run: ``(code, ind, var, skip)`` -- the parsed program,
#: the line cursor, the variables, and the suppression flag.
#:
#: The program is state rather than a fixed text, for two reasons: a
#: ``$name`` is replaced by its value in the line that used it, and
#: ``loop`` counts down by rewriting its own count.  ``snapshot`` already
#: carried it for that reason.
#:
#: ``skip`` is carried because the field exists and the guard reads it, not
#: because it can be observed: a zero ``loop`` sets it and the same step
#: clears it before returning, so no step has ever started with it true.
#: It is kept exactly as it was rather than quietly dropped.
type _Line = tuple[str | int | float, ...]
type _Code = tuple[_Line, ...]
type _Vars = Mapping[str, int | float | str]
type _State = tuple[_Code, int, _Vars, bool]


def _resolve(line: _Line, var: _Vars) -> _Line:
    """Return ``line`` with ``$name`` references replaced by their values.

    The replacement is written back into the line, so a name is looked up
    once however often the line runs again -- which is the language's own
    behaviour, not an optimisation.  A number spelled as text is converted
    at the same time.  An unknown name is a halt: there is no value to put
    in its place.
    """
    out = list(line)
    for i, val in enumerate(out[1:]):
        if isinstance(val, str):
            if val[0] == "$":
                name = val[1:].strip()
                if name not in var:
                    raise HaltError
                out[i + 1] = var[name]
            nxt = out[i + 1]
            if isinstance(nxt, str) and (num := _as_number(nxt)) is not None:
                out[i + 1] = num
    return tuple(out)


def _arith(c: _Line) -> int | float | str:
    """Return the value of a five-token ``make``: two operands and an op."""
    if (o := c[3]) == "++":
        return str(c[2]) + str(c[4])
    name = str(o)
    left, right = _number(c[2], name), _number(c[4], name)
    if o == "+":
        return left + right
    if o == "-":
        return left - right
    if o == "*":
        return left * right
    if right == 0:
        raise HaltError
    return left / right


def _advance(state: _State, answer: str | None = None) -> _State:
    """Return the state after executing the line under the cursor.

    Pure: it reads ``state`` and returns a new one.  ``print`` writes
    nothing here -- the caller does that from the resolved line -- and
    ``input``'s reply arrives as ``answer``.

    The line arrives already resolved, and the state already carries that
    rewrite.  That ordering is the original's: it replaced every ``$name``
    first and only then checked the command had the operands its form
    needs, so a line rejected as malformed still kept its resolved values.

    A blank line and a suppressed one both fall straight through to the
    cursor advance, which is what makes a blank line legal anywhere.
    """
    code, ind, var, skip = state
    c = code[ind]

    if c and not skip:
        # Already resolved by the caller, and already written back: a line
        # rejected below for its shape keeps the values it was given, which
        # is what the original left behind when it validated after
        # rewriting.
        op = c[0]

        if op == "input":
            if len(c) < 2:
                raise ValueError("input requires a prompt")
            var = {**var, "answer": answer if answer is not None else ""}
        elif op == "make":
            if len(c) < 3:
                raise ValueError("make requires a name and a value")
            value = _arith(c) if len(c) == 5 else c[2]
            var = {**var, str(c[1]): value}
        elif op == "if":
            if len(c) < 4:
                raise ValueError("if requires two operands and a comparison")
            lhs, cmp_op, rhs = c[1:4]
            if cmp_op == ">":
                b = _number(lhs, ">") > _number(rhs, ">")
            elif cmp_op == "<":
                b = _number(lhs, "<") < _number(rhs, "<")
            else:
                b = lhs == rhs
            if not b:
                ind = find(code, ind)
        elif op == "loop":
            if len(c) < 2:
                raise ValueError("loop requires a count")
            if c[1]:
                c = (c[0], _number(c[1], "loop") - 1, *c[2:])
                code = (*code[:ind], c, *code[ind + 1 :])
            else:
                ind = find(code, ind)
                skip = True
        elif op == "endloop":
            ind = find(code, ind) + 1

    return (code, ind + 1, var, False)


class _Machine:
    """Per-run Nevermind state: the parsed program, variables, and cursor."""

    def __init__(self, lines: list[str], io: IO) -> None:
        """Parse ``lines`` into comma-separated command tokens."""
        self.io = io
        self.ind = 0
        self.var: dict[str, int | float | str] = {}
        self.skip = False
        self.code: list[list[str | int | float]] = []

        for raw in lines:
            line = raw.lstrip().rstrip("\n").split(",")
            self.code.append([v.replace("*44", ",") for v in line if v])

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.ind >= len(self.code)

    # The VM's language-shaped view: Named variables + line cursor; ip the line, memory
    # the vars.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [
            int(v)
            for v in (self.var[k] for k in sorted(self.var))
            if isinstance(v, (int, float))
        ]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.skip,
            tuple(sorted(self.var.items())),
            tuple(tuple(c) for c in self.code),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (
            tuple(tuple(line) for line in self.code),
            self.ind,
            self.var,
            self.skip,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- ``snapshot`` reads
        all four -- so they stay; the one assignment a step makes is here
        rather than in the rules above.
        """
        code, self.ind, var, self.skip = state
        self.code = [list(line) for line in code]
        self.var = dict(var)

    def step(self) -> None:
        """Execute one line, resolving ``$name`` references in place.

        The two ports live here rather than in the transition: this is the
        shell.  ``print`` writes the resolved line, and ``input`` asks with
        the line's own prompt and hands the reply over.  Both need the line
        *after* its references are resolved, so the resolution runs here
        too and the transition is given the state it produced.
        """
        if self.halted:
            return
        state = self._state
        code, ind, var, skip = state
        line = code[ind]

        answer = None
        if line and not skip:
            # Resolve once, here, and hand the transition the state that
            # rewrite produced: the values stand even if the command turns
            # out to be malformed, exactly as they did before.
            line = _resolve(line, var)
            code = (*code[:ind], line, *code[ind + 1 :])
            state = (code, ind, var, skip)
            # Commit the rewrite now, not after the transition returns: a
            # malformed command raises out of _advance, and the original
            # had already written these values into the line by then.
            self.code = [list(row) for row in code]
            if line[0] == "print":
                self.io.print_str("".join(map(str, line[1:])))
            elif line[0] == "input" and len(line) >= 2:
                answer = self.io.input_str(str(line[1]))

        self._restore(_advance(state, answer))


def run(lines: list[str], io: IO) -> None:
    """Run a Nevermind program given its comma-separated command lines."""
    machine = _Machine(lines, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
