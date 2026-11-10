"""Independent bounded Fargo prefix evaluator; stdlib only, never executed here."""

# ruff: noqa: PT017 -- Independent host-policy probes must not import pytest.

import re
from copy import deepcopy
from dataclasses import dataclass
from unicodedata import decimal


@dataclass(frozen=True)
class CallableValue:
    name: str
    arguments: int
    unevaluated: tuple[int, ...] = ()


@dataclass(frozen=True)
class Definition:
    name: str
    parameters: tuple[str, ...]
    expression: tuple[str, ...]


@dataclass(frozen=True)
class Continuation:
    code: tuple[str, ...]
    offset: int = 0
    label: str = ""
    last: object = 0
    waiting: tuple[tuple[CallableValue, tuple[object, ...]], ...] = ()
    bindings: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class State:
    number: int
    output: int
    line: int
    continuations: tuple[Continuation, ...]


@dataclass(frozen=True)
class Observation:
    state: State | None
    output: str
    cursor: int
    reads: int
    past_end: int
    halted: bool
    error: str | None = None
    message: str | None = None


class RefusalError(Exception):
    def __init__(self, kind, message):
        self.kind, self.message = kind, message
        super().__init__(message)


BUILTINS = {
    name: CallableValue(name, count, (1,) if name == ":" else ())
    for name, count in (
        ("<", 1),
        (">", 1),
        ("&", 2),
        ("|", 2),
        ("^", 2),
        ("[]", 1),
        ("+[]", 2),
        ("[?]", 2),
        ("@", 1),
        ("%", 2),
        ("$", 0),
        (":", 2),
    )
}


def binary(word):
    return bool(word) and set(word) <= {"0", "1"}


def unmark(word):
    return word[1:] if word.startswith(":") and len(word) > 1 else word


def descriptor(definition):
    return CallableValue(
        definition.name,
        len(definition.parameters),
        tuple(
            i for i, name in enumerate(definition.parameters) if unmark(name) != name
        ),
    )


def validate(definition, definitions, bindings=None):
    """Scan one prefix expression, deferring only unresolved raw-call arities."""
    code = definition.expression
    no_outer = f"function {definition.name!r} has no outer call"
    parameters = {
        unmark(p): p.startswith(":") and p != ":" for p in definition.parameters
    }
    if not code:
        raise RefusalError("syntax", no_outer)
    first = code[0]
    if (
        unmark(first) != first
        or binary(first)
        or (first in parameters and not parameters[first])
    ):
        raise RefusalError("syntax", no_outer)
    # Each task is a grammar expression slot; a function expands into its
    # formal slots. Unresolved raw parameters preserve constructor acceptance
    # until actual callable arguments supply their arities at invocation.
    tasks = [False]
    cursor = 0
    while tasks:
        if cursor == len(code):
            raise RefusalError("syntax", no_outer)
        raw = tasks.pop()
        word = code[cursor]
        cursor += 1
        name = unmark(word)
        if raw or name != word or binary(name):
            continue
        if name in parameters:
            if bindings is None:
                if not parameters[name]:
                    continue
                if len(code) - cursor < len(tasks):
                    raise RefusalError("syntax", no_outer)
                return
            value = bindings[name]
            if not isinstance(value, CallableValue):
                continue
            callable_value = value
        elif name in BUILTINS:
            callable_value = BUILTINS[name]
        elif name in definitions:
            callable_value = descriptor(definitions[name])
        else:
            continue
        tasks.extend(
            i in callable_value.unevaluated
            for i in range(callable_value.arguments - 1, -1, -1)
        )
    if cursor != len(code):
        raise RefusalError(
            "syntax", f"function {definition.name!r} has more than one outer call"
        )


def parse(source):
    """Classify lines sequentially; validate definitions against the final table."""
    definitions, calls = {}, []
    for line in source.splitlines():
        words = tuple(line.partition("#")[0].replace("\u200b", "").split())
        if not words:
            continue
        first, *tail = words
        if (
            first in BUILTINS
            or first in definitions
            or binary(first)
            or first.startswith(":")
        ):
            calls.append(words)
            continue
        parameters = []
        known = {*definitions, first}
        start = 0
        while start < len(tail):
            candidate = unmark(tail[start])
            if candidate in BUILTINS or candidate in known or binary(candidate):
                break
            parameters.append(tail[start])
            known.add(candidate)
            start += 1
        definitions[first] = Definition(first, tuple(parameters), tuple(tail[start:]))
    for definition in definitions.values():
        validate(definition, definitions)
    return definitions, tuple(calls)


def constructor_input(text):
    """One token attempt with independently folded Unicode decimal digits."""
    cursor = 0
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    start = cursor
    while cursor < len(text) and not text[cursor].isspace():
        cursor += 1
    if start == cursor:
        return 0, cursor, 0, 1
    token = text[start:cursor]
    value = 0
    if re.fullmatch(r"[+-]?\d(?:_?\d)*", token):
        negative = token.startswith("-")
        for character in token.lstrip("+-"):
            if character != "_":
                value = value * 10 + decimal(character)
        if negative:
            value = -value
    return value, cursor, 1, 0


def thaw(state):
    return [
        {
            "code": f.code,
            "offset": f.offset,
            "label": f.label,
            "last": f.last,
            "waiting": [(fn, list(args)) for fn, args in f.waiting],
            "bindings": dict(f.bindings),
        }
        for f in state.continuations
    ]


def freeze(frames):
    return tuple(
        Continuation(
            f["code"],
            f["offset"],
            f["label"],
            f["last"],
            tuple((fn, tuple(args)) for fn, args in f["waiting"]),
            tuple(f["bindings"].items()),
        )
        for f in frames
    )


def new_frame(code, name="", bindings=()):
    return {
        "code": code,
        "offset": 0,
        "label": name,
        "last": 0,
        "waiting": [],
        "bindings": dict(bindings),
    }


def lookup(name, frame, definitions):
    if name in frame["bindings"]:
        value = frame["bindings"][name]
        if isinstance(value, CallableValue):
            return value
        raise RefusalError("halt", f"calling non-function argument {name!r}")
    if name in BUILTINS:
        return BUILTINS[name]
    if name in definitions:
        return descriptor(definitions[name])
    raise RefusalError("halt", f"calling undefined function {name!r}")


def numeric(value):
    if type(value) is not int:
        raise RefusalError("halt", "expected a number, got an array or function")
    return value


def array(value):
    if type(value) is not tuple:
        raise RefusalError("halt", "expected an array")
    return value


def next_token(frame, definitions):
    word = frame["code"][frame["offset"]]
    frame["offset"] += 1
    if binary(word):
        value = 0
        for bit in word:
            value = 2 * value + (bit == "1")
        return "value", value
    if word.startswith(":") and len(word) > 1:
        return "value", lookup(unmark(word), frame, definitions)
    waiting = frame["waiting"]
    if waiting and len(waiting[-1][1]) in waiting[-1][0].unevaluated:
        return "value", lookup(word, frame, definitions)
    if word in frame["bindings"] and not isinstance(
        frame["bindings"][word], CallableValue
    ):
        return "value", frame["bindings"][word]
    fn = lookup(word, frame, definitions)
    if not fn.arguments:
        return "call", (fn, ())
    waiting.append((fn, []))
    return None


def accept_value(frame, value):
    if not frame["waiting"]:
        frame["last"] = value
        return None
    fn, gathered = frame["waiting"][-1]
    gathered.append(value)
    if len(gathered) < fn.arguments:
        return None
    assert len(gathered) == fn.arguments
    frame["waiting"].pop()
    return "call", (fn, tuple(gathered))


def builtin_call(fn, args, number, output):
    numeric_functions = {
        "<": lambda a: a[0] >> 1,
        ">": lambda a: a[0] << 1,
        "&": lambda a: a[0] & a[1],
        "|": lambda a: a[0] | a[1],
        "^": lambda a: a[0] ^ a[1],
    }
    name = fn.name
    if name in numeric_functions:
        value = numeric_functions[name](tuple(numeric(arg) for arg in args))
    elif name == "[]":
        value = (args[0],)
    elif name == "+[]":
        value = array(args[0]) + array(args[1])
    elif name == "[?]":
        items, at = array(args[0]), numeric(args[1])
        if not 0 <= at < len(items):
            # Diagnostic formatting belongs to the uncommitted transition.
            str(at)
            raise RefusalError("halt", f"array index {at} out of range")
        value = items[at]
    elif name == "@":
        value = (number >> numeric(args[0])) & 1
    elif name == "%":
        at, bit = numeric(args[0]), numeric(args[1]) & 1
        output = output | (1 << at) if bit else output & ~(1 << at)
        value = 0
    elif name == "$":
        return ("value", 0), output, output
    elif name == ":":
        if not numeric(args[0]):
            value = 0
        elif isinstance(args[1], CallableValue):
            if args[1].arguments:
                raise RefusalError(
                    "halt",
                    f"conditional body {args[1].name!r} "
                    f"takes {args[1].arguments} argument(s)",
                )
            return ("call", (args[1], ())), output, None
        else:
            value = args[1]
    else:
        raise AssertionError("unmodeled builtin")
    return ("value", value), output, None


def transition(state, definitions, calls):
    """Clone continuations, process one token/return, then commit atomically."""
    frames = deepcopy(thaw(state))
    output = state.output
    effect = None
    line = state.line
    if not frames:
        return State(state.number, output, line + 1, (Continuation(calls[line]),)), None
    current = frames[-1]
    actions = []
    if current["offset"] == len(current["code"]):
        if current["waiting"]:
            raise RefusalError("syntax", "call wants more args")
        finished = frames.pop()
        if frames:
            actions.append(("value", finished["last"]))
    else:
        action = next_token(current, definitions)
        if action is not None:
            actions.append(action)
    while actions:
        kind, payload = actions.pop()
        if kind == "value":
            action = accept_value(frames[-1], payload)
        else:
            fn, args = payload
            if fn.name not in BUILTINS:
                definition = definitions[fn.name]
                bindings = dict(
                    zip((unmark(p) for p in definition.parameters), args, strict=True)
                )
                validate(definition, definitions, bindings)
                frames.append(
                    new_frame(definition.expression, fn.name, bindings.items())
                )
                continue
            action, output, printed = builtin_call(fn, args, state.number, output)
            if effect is None:
                effect = printed
        if action is not None:
            actions.append(action)
    return State(state.number, output, line, freeze(frames)), effect


def model(source, stdin="", cap=64):
    """Include explicit failed boundaries and three posthalt observations."""
    try:
        definitions, calls = parse(source)
    except RefusalError as refusal:
        return [
            Observation(
                None,
                "",
                0,
                0,
                0,
                halted=False,
                error=refusal.kind,
                message=refusal.message,
            )
        ]
    number, cursor, reads, past = constructor_input(stdin)
    state = State(number, 0, 0, ())
    text = ""

    def observation(error=None, message=None):
        return Observation(
            state,
            text,
            cursor,
            reads,
            past,
            state.line == len(calls) and not state.continuations,
            error,
            message,
        )

    rows = [observation()]
    for _ in range(cap):
        if rows[-1].halted:
            rows.extend([observation()] * 3)
            break
        try:
            changed, printed = transition(state, definitions, calls)
        except RefusalError as refusal:
            rows.append(observation(refusal.kind, refusal.message))
            break
        except ValueError as failure:
            assert str(failure).startswith("Exceeds the limit (")
            rows.append(observation("limit", str(failure)))
            break
        state = changed
        if printed is not None:
            try:
                text += str(printed)
            except ValueError as failure:
                assert str(failure).startswith("Exceeds the limit (")
                rows.append(observation("limit", str(failure)))
                break
        rows.append(observation())
    else:
        if rows[-1].halted:
            rows.extend([observation()] * 3)
    return rows
