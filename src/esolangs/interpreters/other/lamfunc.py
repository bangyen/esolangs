"""Interpreter for Lamfunc.

A functional prefix-call language: a program is a list of function
definitions (``F name - code`` on one line each) followed by a top-level
call sequence.  Values are integers (decimal or ``0b`` binary literals),
functions, and strings used as variable names.  ``.f`` returns the function
``f`` without calling it, and a call with fewer arguments than the
function's arity returns a lambda that takes the rest, so partial
application is expressible.

A call ``f g x y h i`` means ``f(g(x(), y()), h()); i()``: each argument is
itself a full prefix expression consumed by that expression's own arity.
The eight builtins:

- ``p x`` prints ``x`` (as binary for a number) and returns it.
- ``eq x y`` returns 1 if ``x == y`` else 0.
- ``i x y z`` returns ``y`` if ``x`` is nonzero else ``z``.
- ``cb x y`` combines the bits of ``x`` and ``y`` (``0b10`` and ``0b110``
  give ``0b10110``).
- ``lb x`` returns the last bit of ``x``.
- ``fb x`` returns all but the last bit of ``x``.
- ``vs x y`` sets the variable named ``x`` to ``y`` and returns ``y``.
- ``vg x`` returns the value of the variable named ``x`` (0 if undefined).

Decisions for gaps in the wiki spec (documented):
- a user function's ``return`` value is the value of the last evaluated
  expression in its body (the wiki shows ``Return`` only in Procedure; here
  the last expression's value is the function's result, matching the prefix
  model);
- redefining a function, calling an undefined function, applying a
  non-function, or a top-level call with more arguments than a function's
  arity (an un-consumed dangling argument) is a malformed program
  (:class:`ValueError`); an invalid runtime operation (e.g. printing a
  function, or an overflowed bit combine) raises
  :class:`~esolangs.exceptions.HaltError`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


@dataclass
class _Def:
    """One ``F name - code`` function definition."""

    params: list[str]
    body: list[str]


class _Func:
    """A callable: a builtin, a user function, or a partial application."""

    __slots__ = ("arity", "body", "given", "name", "orig", "params")

    def __init__(
        self,
        name: str,
        arity: int,
        body: list[str] | None = None,
        params: list[str] | None = None,
        given: list[object] | None = None,
        orig: _Func | None = None,
    ) -> None:
        self.name = name
        self.arity = arity
        self.body = body
        self.params = params
        self.given = given or []
        self.orig = orig


_BUILTINS: dict[str, _Func] = {
    "p": _Func("p", 1),
    "eq": _Func("eq", 2),
    "i": _Func("i", 3),
    "cb": _Func("cb", 2),
    "lb": _Func("lb", 1),
    "fb": _Func("fb", 1),
    "vs": _Func("vs", 2),
    "vg": _Func("vg", 1),
}


def _is_int(tok: str) -> bool:
    if tok.startswith("0b"):
        return bool(tok[2:]) and all(c in "01" for c in tok[2:])
    return tok.isdigit()


def _parse_int(tok: str) -> int:
    return int(tok, 2) if tok.startswith("0b") else int(tok)


def _to_binary(value: int) -> str:
    """Print an integer as its binary representation (0 as ``0``)."""
    return bin(value)[2:] if value else "0"


def _as_int(value: object) -> int:
    """Coerce a Lamfunc value to an integer (the bit-builtins' operand)."""
    if isinstance(value, bool):
        return int(value)  # pragma: no cover - Lamfunc never produces a bool
    if isinstance(value, int):
        return value
    raise HaltError(f"expected a number, got {value!r}")


class _Thunk:
    """An unevaluated ``i`` branch: evaluate only when selected."""

    __slots__ = ("end", "machine", "start", "tokens")

    def __init__(
        self, machine: _Machine, tokens: list[str], start: int, end: int
    ) -> None:
        self.machine = machine
        self.tokens = tokens
        self.start = start
        self.end = end

    def force(self) -> object:
        value, _ = self.machine._eval(self.tokens, self.start)  # noqa: SLF001
        return value


class _Machine:
    """One Lamfunc run: the definitions, variables, and evaluation stack."""

    def __init__(self, io: IO) -> None:
        self.io = io
        self.defs: dict[str, _Def] = {}
        self.vars: dict[str, object] = {}
        self._halted = False

    @property
    def halted(self) -> bool:
        return self._halted  # pragma: no cover - no step-capable wrapper yet

    def _arity(self, name: str) -> int:
        """Return ``name``'s arity (a builtin's fixed arity, or a def's)."""
        if name in _BUILTINS:
            return _BUILTINS[name].arity
        if name in self.defs:
            return len(self.defs[name].params)
        raise HaltError(f"calling undefined function {name!r}")

    def _lookup(self, name: str) -> _Func:
        if name in _BUILTINS:
            return _BUILTINS[name]
        if name in self.defs:
            d = self.defs[name]
            return _Func(name, len(d.params), d.body, d.params)
        raise HaltError(  # pragma: no cover - callers only look up known names
            f"calling undefined function {name!r}"
        )

    # -- the core: evaluate one prefix expression, returning (value, consumed)

    def _eval(self, tokens: list[str], i: int) -> tuple[object, int]:
        """Evaluate ``tokens[i:]``; return ``(value, tokens consumed)``."""
        tok = tokens[i]
        if tok.startswith("."):
            name = tok[1:]
            # a bound parameter (e.g. ``id f - .f``) returns its value
            if name in self.vars:
                return self.vars[name], 1
            return _Func(name, self._arity(name), *self._def_fields(name)), 1
        if _is_int(tok):
            return _parse_int(tok), 1
        # a bound variable holding a function is a call site (``a b`` calls a)
        if tok in self.vars and isinstance(self.vars[tok], _Func):
            fn = cast(_Func, self.vars[tok])
        elif tok in _BUILTINS or tok in self.defs:
            fn = self._lookup(tok)
        # a bound variable: return its value (a number or a string)
        elif tok in self.vars:
            return self.vars[tok], 1
        # an undefined identifier followed by more tokens is a call to an
        # undefined function; a bare one is a variable NAME (for vs/vg)
        elif i + 1 < len(tokens):
            raise HaltError(f"calling undefined function {tok!r}")
        else:
            return tok, 1

        arity = fn.arity
        args: list[object] = []
        pos = i + 1
        for _ in range(arity):
            if pos >= len(tokens):
                # partial application: return a lambda for the missing args
                return self._partial(fn, args), pos - i
            # vs/vg take their variable NAME as a literal token, never a value
            if fn.name in ("vs", "vg") and not args:
                args.append(tokens[pos])
                pos += 1
                continue
            # i is lazy in its second and third arguments: only the chosen
            # branch is evaluated, so a branch may recurse (the while loop).
            if fn.name == "i" and len(args) >= 1:
                end = self._scan(tokens, pos)
                args.append(_Thunk(self, tokens, pos, end))
                pos = end
                continue
            value, consumed = self._eval(tokens, pos)
            args.append(value)
            pos += consumed
        return self._apply(fn, args), pos - i

    def _scan(self, tokens: list[str], i: int) -> int:
        """Return how many tokens the expression at ``i`` occupies."""
        tok = tokens[i]
        if (
            tok.startswith(".")
            or _is_int(tok)
            or tok in self.vars
            or (tok not in _BUILTINS and tok not in self.defs)
        ):
            return i + 1
        fn = self._lookup(tok)
        end = i + 1
        for _ in range(fn.arity):
            if end >= len(tokens):
                return end
            end = self._scan(tokens, end)
        return end

    def _def_fields(self, name: str) -> tuple[list[str] | None, list[str] | None]:
        d = self.defs.get(name)
        return (d.body if d else None, d.params if d else None)

    def _partial(self, fn: _Func, given: list[object]) -> _Func:
        """Build a lambda that, when called with the remaining args, calls fn."""
        return _Func(
            fn.name + "..",
            fn.arity - len(given),
            fn.body,
            fn.params,
            given=given,
            orig=fn,
        )

    def _apply(self, fn: _Func, args: list[object]) -> object:
        """Apply a builtin or user function to its (evaluated) arguments."""
        if fn.name == "p":
            self.io.print_str(_print_value(args[0]))
            return args[0]
        if fn.name == "eq":
            return 1 if args[0] == args[1] else 0
        if fn.name == "i":
            cond, branch_t, branch_f = args[0], args[1], args[2]
            chosen = branch_t if cond != 0 else branch_f
            if isinstance(chosen, _Thunk):
                return chosen.force()
            return chosen
        if fn.name == "cb":
            x, y = _as_int(args[0]), _as_int(args[1])
            if x < 0 or y < 0:  # pragma: no cover - Lamfunc values are never negative
                raise HaltError("cb of a negative number is undefined")
            return int(bin(x)[2:] + bin(y)[2:], 2) if (x or y) else 0
        if fn.name == "lb":
            return _as_int(args[0]) & 1
        if fn.name == "fb":
            return _as_int(args[0]) >> 1
        if fn.name == "vs":
            self.vars[str(args[0])] = args[1]
            return args[1]
        if fn.name == "vg":
            return self.vars.get(str(args[0]), 0)

        # user-defined (or a partial application completing): bind params to
        # args (given + new) in a fresh scope and run the body
        if fn.orig is not None:
            return self._apply(fn.orig, fn.given + args)
        saved = {p: self.vars.get(p) for p in (fn.params or [])}
        self.vars.update(dict(zip(fn.params or [], args, strict=True)))
        result: object = 0
        i = 0
        body = fn.body or []
        while i < len(body):
            result, consumed = self._eval(body, i)
            i += consumed
        for p in fn.params or []:
            self.vars.pop(p, None)
        self.vars.update({p: v for p, v in saved.items() if v is not None})
        return result

    def run_main(self, tokens: list[str]) -> None:
        """Evaluate the top-level call sequence."""
        i = 0
        while i < len(tokens):
            result, consumed = self._eval(tokens, i)
            if consumed == 0:  # pragma: no cover - _eval always consumes a token
                raise HaltError("a dangling partial application at the top level")
            i += consumed
            # a partial application absorbs the remaining tokens as its args
            while isinstance(result, _Func) and result.arity > 0 and i < len(tokens):
                args: list[object] = []
                for _ in range(result.arity):
                    value, consumed = self._eval(tokens, i)
                    args.append(value)
                    i += consumed
                result = self._apply(result, args)
            self._halted = i >= len(tokens)


def _print_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"  # pragma: no cover - Lamfunc never produces a bool
    if isinstance(value, int):
        return _to_binary(value)
    if isinstance(value, _Func):
        return value.name
    return str(value)


def _parse_program(code: str) -> tuple[dict[str, _Def], list[str]]:
    """Split the program into definitions and the top-level call sequence.

    A definition is ``F name - code`` on one line; anything else is part of
    the top-level sequence.  Redefinition is malformed (:class:`ValueError`).
    """
    defs: dict[str, _Def] = {}
    main: list[str] = []
    for line in code.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("F "):
            rest = line[2:]
            if "-" not in rest:
                raise ValueError("function definition must contain '-'")
            head, _, body = rest.partition("-")
            name = head.split()[0]
            params = head.split()[1:]
            if name in defs:
                raise ValueError(f"function {name!r} redefined")
            defs[name] = _Def(params, body.split())
        else:
            main.extend(line.split())
    return defs, main


def run(code: str, io: IO) -> None:
    """Run a Lamfunc program."""
    machine = _Machine(io)
    defs, main = _parse_program(code)
    machine.defs = defs
    machine.run_main(main)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
