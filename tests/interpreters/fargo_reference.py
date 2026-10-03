"""Recursive Fargo expressions, separate from the production frame machine."""

import re
from contextlib import suppress

from esolangs.exceptions import HaltError

ARITY = {
    "<": 1,
    ">": 1,
    "&": 2,
    "|": 2,
    "^": 2,
    "[]": 1,
    "+[]": 2,
    "[?]": 2,
    "@": 1,
    "%": 2,
    "$": 0,
    ":": 2,
}


class LimitError(Exception):
    pass


class CycleError(Exception):
    pass


class DeferredArityError(Exception):
    pass


class Reference:
    def __init__(self, code, stdin, fuel=10000):
        self.defs = {}
        self.lines = []
        self.number = self.output = 0
        self.text = ""
        self.offset = 0
        self.fuel = fuel
        self.active = set()
        for line in code.splitlines():
            tokens = line.partition("#")[0].replace("\u200b", "").split()
            if not tokens:
                continue
            first, *tail = tokens
            if (
                first in ARITY
                or first in self.defs
                or self.literal(first)
                or first.startswith(":")
            ):
                self.lines.append(tokens)
                continue
            parameters = []
            known = set(ARITY) | set(self.defs) | {first}
            i = 0
            for token in tail:
                bare = token[1:] if token.startswith(":") and len(token) > 1 else token
                if bare in known or self.literal(bare):
                    break
                parameters.append(token)
                known.add(bare)
                i += 1
            body = tail[i:]
            if not body:
                raise ValueError("missing outer call")
            self.defs[first] = (parameters, body)
        for parameters, body in self.defs.values():
            unknown = {p.removeprefix(":"): ("unknown", p) for p in parameters}
            with suppress(DeferredArityError):
                self.validate(body, unknown)
        token = re.search(r"\S+", stdin)
        if token:
            self.offset = token.end()
            with suppress(ValueError):
                self.number = int(token.group())

    def literal(self, token):
        return re.fullmatch("[01]+", token) is not None

    def raw(self, name, env):
        if name in env:
            value = env[name]
            if not (type(value) is tuple and value[0] == "function"):
                raise HaltError("non-function argument")
            return value
        if name in ARITY or name in self.defs:
            return ("function", name)
        raise HaltError("undefined function")

    def numeric(self, value):
        if type(value) is not int:
            raise HaltError("expected number")
        return value

    def array(self, value):
        if type(value) is not list:
            raise HaltError("expected array")
        return value

    def expression(self, tokens, position, env, *, raw=False):
        self.fuel -= 1
        if self.fuel < 0:
            raise LimitError
        if position == len(tokens):
            raise ValueError("missing arguments")
        name = tokens[position]
        position += 1
        if self.literal(name):
            return int(name, 2), position
        if name.startswith(":") and len(name) > 1:
            return self.raw(name[1:], env), position
        if raw:
            return self.raw(name, env), position
        value = env.get(name, ("function", name))
        if not (type(value) is tuple and value[0] == "function"):
            return value, position
        function = value[1]
        if function in ARITY:
            arity = ARITY[function]
            raw_slots = {1} if function == ":" else set()
        elif function in self.defs:
            parameters, _ = self.defs[function]
            arity = len(parameters)
            raw_slots = {i for i, p in enumerate(parameters) if p.startswith(":")}
        else:
            raise HaltError("undefined function")
        arguments = []
        for i in range(arity):
            value, position = self.expression(tokens, position, env, raw=i in raw_slots)
            arguments.append(value)
        return self.apply(function, arguments), position

    def shape(self, tokens, position, env, *, raw=False, owed=0):
        if position == len(tokens):
            raise ValueError("missing arguments")
        name = tokens[position]
        position += 1
        if self.literal(name) or raw or (name.startswith(":") and len(name) > 1):
            return position
        value = env.get(name, ("function", name))
        if type(value) is tuple and value[0] == "unknown":
            if len(tokens) - position < owed:
                raise ValueError("missing arguments")
            raise DeferredArityError
        if not (type(value) is tuple and value[0] == "function"):
            return position
        function = value[1]
        if function in ARITY:
            arity = ARITY[function]
            raw_slots = {1} if function == ":" else set()
        elif function in self.defs:
            parameters, _ = self.defs[function]
            arity = len(parameters)
            raw_slots = {i for i, p in enumerate(parameters) if p.startswith(":")}
        else:
            return position
        for i in range(arity):
            position = self.shape(
                tokens, position, env, raw=i in raw_slots, owed=owed + arity - i - 1
            )
        return position

    def validate(self, tokens, env):
        if self.shape(tokens, 0, env) != len(tokens):
            raise ValueError("multiple outer calls")

    def frozen(self, value):
        return (
            tuple(self.frozen(item) for item in value) if type(value) is list else value
        )

    def apply(self, name, args):
        if name in self.defs:
            parameters, tokens = self.defs[name]
            env = {
                p.removeprefix(":"): arg
                for p, arg in zip(parameters, args, strict=True)
            }
            self.validate(tokens, env)
            key = (name, tuple(self.frozen(arg) for arg in args))
            if key in self.active:
                raise CycleError
            self.active.add(key)
            try:
                value, _ = self.expression(tokens, 0, env)
                return value
            finally:
                self.active.remove(key)
        if name == "[]":
            return [args[0]]
        if name == "+[]":
            return self.array(args[0]) + self.array(args[1])
        if name == "[?]":
            array = self.array(args[0])
            index = self.numeric(args[1])
            if index < 0 or index >= len(array):
                raise HaltError("array index")
            return array[index]
        if name == ":":
            if not self.numeric(args[0]):
                return 0
            body = args[1]
            if not (type(body) is tuple and body[0] == "function"):
                return body
            function = body[1]
            arity = (
                ARITY[function] if function in ARITY else len(self.defs[function][0])
            )
            if arity:
                raise HaltError("conditional arity")
            return self.apply(function, [])
        if name == "$":
            self.text += str(self.output)
            return 0
        x = self.numeric(args[0])
        if name == "<":
            return x >> 1
        if name == ">":
            return x << 1
        if name == "@":
            return self.number // (2**x) % 2
        y = self.numeric(args[1])
        if name == "&":
            return x & y
        if name == "|":
            return x | y
        if name == "^":
            return x ^ y
        if name == "%":
            mask = 2**x
            self.output = (
                (self.output // (2 * mask)) * (2 * mask)
                + self.output % mask
                + (y % 2) * mask
            )
            return 0
        raise AssertionError(name)

    def execute(self):
        for tokens in self.lines:
            position = 0
            while position < len(tokens):
                _, position = self.expression(tokens, position, {})
