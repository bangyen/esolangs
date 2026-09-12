r"""Interpreter for Nevermind."""

import sys
from collections.abc import Mapping, Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def find(code: Sequence[Sequence[str | int | float]], ind: int) -> int:
    r"""Return the index of the matching ``if``/``loop`` partner for."""
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
        # A blank line parses to no.
        # scan for the partner has to.
        # command out of it.
        if line := code[ind]:
            if line[0] == op:
                num += move
            elif line[0] == match:
                num -= move
        ind += move
    return ind - 1


def _as_number(value: str) -> int | float | None:
    r"""Return ``value`` as a number, or ``None`` if it does not spell one."""
    if not value.isascii():
        return None
    if value.isdigit():
        return int(value)
    whole, dot, frac = value.partition(".")
    if dot and whole.isdigit() and frac.isdigit():
        # Only a spelling that survives.
        # float back without the.
        # print as "2.5" and silently.
        number = float(value)
        if str(number) == value:
            return number
    return None


def _number(value: str | int | float, op: str) -> int | float:
    r"""Return ``value`` as a number, halting if it is not one."""
    if isinstance(value, str):
        raise HaltError(f"{op} needs a number, got {value!r}")
    return value


# : One instant of a run:.
# : the line cursor, the.
# :.
# : The program is state rather.
# : ``$name`` is replaced by.
# : ``loop`` counts down by.
#: carried it for that reason.
# :.
# : ``skip`` is carried because.
# : because it can be observed:.
# : clears it before returning,.
# : It is kept exactly as it.
type _Line = tuple[str | int | float, ...]
type _Code = tuple[_Line, ...]
type _Vars = Mapping[str, int | float | str]
type _State = tuple[_Code, int, _Vars, bool]


def _resolve(line: _Line, var: _Vars) -> _Line:
    r"""Return ``line`` with ``$name`` references replaced by their values."""
    out = list(line)
    for i, val in enumerate(out[1:]):
        if isinstance(val, str):
            if val[0] == "$":
                name = val[1:].strip()
                if name not in var:
                    known = ", ".join(sorted(var)) or "none are defined yet"
                    raise HaltError(f"${name} is not a defined variable ({known})")
                out[i + 1] = var[name]
            nxt = out[i + 1]
            if isinstance(nxt, str) and (num := _as_number(nxt)) is not None:
                out[i + 1] = num
    return tuple(out)


def _arith(c: _Line) -> int | float | str:
    r"""Return the value of a five-token ``make``: two operands and an op."""
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
        raise HaltError(f"division by zero: {left} {o} {right}")
    return left / right


def _advance(state: _State, answer: str | None = None) -> _State:
    r"""Return the state after executing the line under the cursor."""
    code, ind, var, skip = state
    c = code[ind]

    if c and not skip:
        # Already resolved by the.
        # rejected below for its shape.
        # is what the original left.
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
    r"""Per-run Nevermind state: the parsed program, variables, and cursor."""

    def __init__(self, lines: list[str], io: IO) -> None:
        r"""Parse ``lines`` into comma-separated command tokens."""
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
        r"""Whether the cursor has reached the end of the program."""
        return self.ind >= len(self.code)

    # The VM's language-shaped.
    # the vars.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [
            int(v)
            for v in (self.var[k] for k in sorted(self.var))
            if isinstance(v, (int, float))
        ]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.skip,
            tuple(sorted(self.var.items())),
            tuple(tuple(c) for c in self.code),
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (
            tuple(tuple(line) for line in self.code),
            self.ind,
            self.var,
            self.skip,
        )

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        code, self.ind, var, self.skip = state
        self.code = [list(line) for line in code]
        self.var = dict(var)

    def step(self) -> None:
        r"""Execute one line, resolving ``$name`` references in place."""
        if self.halted:
            return
        state = self._state
        code, ind, var, skip = state
        line = code[ind]

        answer = None
        if line and not skip:
            # Resolve once, here, and hand.
            # rewrite produced: the values.
            # out to be malformed, exactly.
            line = _resolve(line, var)
            code = (*code[:ind], line, *code[ind + 1 :])
            state = (code, ind, var, skip)
            # Commit the rewrite now, not.
            # malformed command raises out.
            # had already written these.
            self.code = [list(row) for row in code]
            if line[0] == "print":
                self.io.print_str("".join(map(str, line[1:])))
            elif line[0] == "input" and len(line) >= 2:
                answer = self.io.input_str(str(line[1]))

        self._restore(_advance(state, answer))


def run(lines: list[str], io: IO) -> None:
    r"""Run a Nevermind program given its comma-separated command lines."""
    machine = _Machine(lines, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
