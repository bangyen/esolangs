"""Interpreter for ZTOALC L.

Programs are a list of lines; line 1 holds the initial pointer.  Execution
visits line ``v`` when the Collatz step equals ``v``, halting when the value
reaches 1.  Commands print, jump, assign, add, and subtract using the current
value as an expression.

Expressions follow the wiki's grammar: ``input`` (read a character's ASCII
value), a variable, a number, ``[size]`` to create an array of ``size``
elements, and ``array[index]`` where ``array`` is any expression evaluating
to an array -- so nested indexing and arrays-of-arrays (an element that is
itself an array) are supported.  A command missing a required operand, an
empty or unbalanced index expression (``a[]``, ``a[1``), is a malformed
program and is rejected with :class:`ValueError`; referencing an undefined
variable, indexing out of range, reaching a negative pointer, or using an
array where a number is required are invalid operations that halt the
program with :class:`~esolangs.exceptions.HaltError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the code, variables, and
Collatz pointer), so it is step-capable: ``step()`` executes the line at
the current pointer and advances it to the next line in the trajectory,
and ``halted`` is true once the pointer reaches 1.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

Value = int | list["Value"]


def _is_int(tok: str) -> bool:
    """Whether ``tok`` is a decimal integer literal (possibly negative)."""
    return tok.lstrip("-").isdigit() and tok != "-"


def _as_int(value: Value) -> int:
    """Require ``value`` to be an integer, halting on an array."""
    if not isinstance(value, int):
        raise HaltError
    return value


def _freeze(value: Value) -> object:
    """Return a hashable form of ``value`` (arrays become nested tuples)."""
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


class _Machine:
    """One ZTOALC L run: the code, variables, and Collatz pointer."""

    def __init__(self, code: list[str], io: IO) -> None:
        if not code:
            raise ValueError("ZTOALC L program cannot be empty")
        self.io = io
        self.code = code
        self.ptr = int(code[0])
        self.var: dict[str, Value] = {}

    @property
    def halted(self) -> bool:
        """Whether the Collatz trajectory has reached 1."""
        return self.ptr == 1

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ptr,
            tuple(sorted((k, _freeze(v)) for k, v in self.var.items())),
            self.io.position(),
        )

    def _atom(self, exp: str, pos: int) -> tuple[Value, int]:
        """Parse the leading atom of ``exp`` from ``pos``.

        Returns ``(value, next_position)``.  An atom is ``[expr]`` (array
        creation), the ``input`` keyword, a number, or a variable name.
        """
        if not exp:
            raise ValueError("missing expression")
        if exp[pos] == "[":
            size, pos = self._eval(exp, pos + 1)
            pos += 1  # the closing ']'
            return [0] * _as_int(size), pos
        j = pos
        while j < len(exp) and exp[j] not in "[]":
            j += 1
        tok = exp[pos:j]
        if tok == "input":
            return self.io.input_char(), j
        if _is_int(tok):
            return int(tok), j
        if tok in self.var:
            return self.var[tok], j
        raise HaltError

    def _eval(self, exp: str, pos: int) -> tuple[Value, int]:
        """Evaluate the expression ``exp`` from ``pos``, returning (value, pos).

        An expression is an atom followed by any number of ``[index]``
        indexings, so ``array[index]`` with a general ``array`` expression
        (including further indexings) works.
        """
        value, pos = self._atom(exp, pos)
        while pos < len(exp) and exp[pos] == "[":
            index, pos = self._eval(exp, pos + 1)
            pos += 1  # the closing ']'
            if not isinstance(value, list):
                raise HaltError
            i = _as_int(index)
            if i < 0 or i >= len(value):
                raise HaltError
            value = value[i]
        return value, pos

    def _val(self, exp: str) -> Value:
        """Evaluate the expression ``exp``."""
        value, _ = self._eval(exp, 0)
        return value

    @staticmethod
    def _operand(lst: list[str], n: int) -> str:
        """Return the ``n``-th token of a command, rejecting a missing one."""
        if n >= len(lst):
            raise ValueError("missing operand in " + " ".join(lst))
        return lst[n]

    @staticmethod
    def _split(lhs: str) -> tuple[str, list[str]]:
        """Split ``lhs`` into its base atom and index-expression strings."""
        atom = lhs[: lhs.find("[")]
        indexes: list[str] = []
        pos = lhs.find("[")
        while pos < len(lhs):
            depth = 1
            j = pos + 1
            while depth:
                if j >= len(lhs):
                    raise ValueError(f"unbalanced brackets in {lhs!r}")
                if lhs[j] == "[":
                    depth += 1
                elif lhs[j] == "]":
                    depth -= 1
                j += 1
            indexes.append(lhs[pos + 1 : j - 1])
            pos = j
        return atom, indexes

    def _store(self, lhs: str, value: Value) -> None:
        """Assign ``value`` to ``lhs`` (a name or an ``array[index]``)."""
        if "[" not in lhs:
            self.var[lhs] = value
            return
        atom, indexes = self._split(lhs)
        target, _ = self._atom(atom, 0)
        for idx_exp in indexes[:-1]:
            if not isinstance(target, list):
                raise HaltError
            i = _as_int(self._eval(idx_exp, 0)[0])
            if i < 0 or i >= len(target):
                raise HaltError
            target = target[i]
        if not isinstance(target, list):
            raise HaltError
        i = _as_int(self._eval(indexes[-1], 0)[0])
        if i < 0 or i >= len(target):
            raise HaltError
        target[i] = value

    def step(self) -> None:
        """Execute the line at ``ptr`` and advance to the next in trajectory."""
        if self.halted:
            return
        ptr = self.ptr
        p = ptr - 1
        if p < 0:
            raise HaltError
        ins = self.code[p] if p < len(self.code) else ""
        lst = ins.split()
        if not lst:
            pass
        elif lst[0] == "print":
            value = _as_int(self._val(self._operand(lst, 1)))
            if not 0 <= value <= 0x10FFFF:
                raise HaltError
            self.io.print_char(chr(value))
        elif lst[0] == "jump":
            if _as_int(self._val(self._operand(lst, 2))):
                self.ptr = ptr + 1
                return
        else:
            op = lst[1] if len(lst) > 1 else ""
            if op == "=":
                self._store(self._operand(lst, 0), self._val(self._operand(lst, 2)))
            elif op in ("+=", "+"):
                self._store(
                    self._operand(lst, 0),
                    _as_int(self._val(self._operand(lst, 0)))
                    + _as_int(self._val(self._operand(lst, 2))),
                )
            elif op in ("-=", "-"):
                self._store(
                    self._operand(lst, 0),
                    _as_int(self._val(self._operand(lst, 0)))
                    - _as_int(self._val(self._operand(lst, 2))),
                )

        if ptr % 2:
            self.ptr = 3 * ptr + 1
        else:
            self.ptr = ptr // 2


def run(code: list[str], io: IO) -> None:
    """Run a ZTOALC L program, following the Collatz trajectory of line 1."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
