"""Independent finite Forbin graph machine with explicit physical IO phases."""
# Source-only draft API: concise names are shared with the root price driver.
# ruff: noqa: N818, FBT002

from copy import deepcopy
from dataclasses import dataclass, replace
from itertools import product


class ModelHalt(Exception):
    pass


class NeedByte(Exception):
    pass


class Refusal(Exception):
    pass


class ModelBudgetError(Exception):
    """The source-only draft cannot certify this unbounded inner evaluation."""

    pass


@dataclass(frozen=True)
class Closure:
    function: object
    environment: int


@dataclass
class Environment:
    function: object
    parent: int | None
    values: dict


@dataclass(frozen=True)
class Frame:
    function: object
    environment: int
    position: int = 0
    rows: tuple | None = None
    names: tuple = ()
    index: int = 0
    started: bool = False
    body_position: int = 0


@dataclass
class State:
    frames: list
    environments: list
    bits: tuple = ()
    reads: int = 0


class Port:
    def __init__(self, text="", refuse_read=None, refuse_write=None, partial=False):
        self.text = text
        self.position = 0
        self.reads = 0
        self.past_end = 0
        self.output = ""
        self.newline = False
        self.events = []
        self.read_attempts = 0
        self.write_attempts = 0
        self.refuse_read = refuse_read
        self.refuse_write = refuse_write
        self.partial = partial

    def read(self):
        self.read_attempts += 1
        if self.read_attempts == self.refuse_read:
            self.events.append(("refuse_read",))
            raise Refusal
        if self.position == len(self.text):
            self.past_end += 1
            self.events.append(("eof",))
            raise EOFError
        value = ord(self.text[self.position])
        self.position += 1
        self.reads += 1
        self.newline = False
        self.events.append(("read", value))
        return value

    def write(self, char):
        self.write_attempts += 1
        if self.write_attempts == self.refuse_write:
            if self.partial:
                self.output += char
            self.events.append(("refuse_write", char, self.partial))
            raise Refusal
        self.output += char
        self.newline = char != "\n"
        self.events.append(("write", char))


class Attempt:
    def __init__(self, state, functions, supplied=()):
        self.state = deepcopy(state)
        self.functions = functions
        self.supplied = supplied
        self.consumed = 0
        self.effects = []
        self.fuel = 10000

    def enter(self, closure, arguments):
        values = dict.fromkeys(closure.function.args, 0)
        values.update(zip(closure.function.args, arguments, strict=False))
        environment = len(self.state.environments)
        self.state.environments.append(
            Environment(closure.function, closure.environment, values)
        )
        return Frame(closure.function, environment)

    def lookup(self, frame, name):
        pointer = frame.environment
        root = pointer
        while pointer is not None:
            scope = self.state.environments[pointer]
            if name in scope.values:
                return scope.values[name]
            nested = dict(scope.function.nested) if scope.function is not None else {}
            if name in nested:
                return Closure(nested[name], pointer)
            root = pointer
            pointer = scope.parent
        if name in ("in", "out"):
            return name
        if name in self.functions:
            return Closure(self.functions[name], root)
        raise ModelHalt(("undeclared", name))

    def bind(self, frame, name, value):
        if name == "_":
            return
        pointer = frame.environment
        while (
            pointer is not None and name not in self.state.environments[pointer].values
        ):
            pointer = self.state.environments[pointer].parent
        if pointer is None:
            pointer = frame.environment
        self.state.environments[pointer].values[name] = value

    def value(self, node, frame):
        kind = node[0]
        if kind == "bit":
            return node[1]
        if kind == "name":
            return self.lookup(frame, node[1])
        if kind == "function":
            return Closure(node[1], frame.environment)
        if kind == "not":
            value = self.value(node[1], frame)
            if value not in (0, 1):
                raise ModelHalt("not bit")
            return 1 - value
        function = self.value(node[1], frame)
        arguments = [self.value(argument, frame) for argument in node[2]]
        return self.call(function, arguments)

    def call(self, function, arguments):
        if isinstance(function, Closure):
            frames = [self.enter(function, arguments)]
            answer = None
            while frames:
                frames, returned = self.tick(frames)
                if not frames:
                    answer = returned
            return 0 if answer is None else answer
        if function == "in":
            if not self.state.bits:
                if self.consumed == len(self.supplied):
                    raise NeedByte
                byte = self.supplied[self.consumed]
                self.consumed += 1
                self.state.bits = tuple(
                    (byte >> shift) & 1 for shift in range(7, -1, -1)
                )
            bit, *tail = self.state.bits
            self.state.bits = tuple(tail)
            self.state.reads += 1
            return bit
        if function == "out":
            if len(arguments) != 8 or any(bit not in (0, 1) for bit in arguments):
                raise ModelHalt("output bits")
            value = 0
            for bit in arguments:
                value = 2 * value + bit
            self.effects.append(chr(value))
            return 0
        raise ModelHalt("not callable")

    def loop(self, spec, frame):
        if spec[0] == "range":
            lower = self.value(spec[2], frame)
            upper = self.value(spec[3], frame)
            if type(lower) is not int or type(upper) is not int:
                raise ModelHalt("range bound")
            return tuple((value,) for value in range(lower, upper + 1)), (spec[1],)
        rows = []
        for group in spec[2]:
            for choices in product((0, 1), repeat=sum(item is None for item in group)):
                iterator = iter(choices)
                rows.append(
                    tuple(
                        next(iterator) if item is None else self.value(item, frame)
                        for item in group
                    )
                )
        return tuple(rows), spec[1]

    def statement(self, statement, frames, body=False):
        frame = frames[-1]
        advanced = replace(
            frame,
            **(
                {"body_position": frame.body_position + 1}
                if body
                else {"position": frame.position + 1}
            ),
        )
        prefix = frames[:-1]
        kind = statement[0]
        if kind == "return":
            return prefix, self.value(statement[1], frame)
        if kind == "assign":
            names, nodes = statement[1:]
            values = nodes * len(names) if len(nodes) == 1 else nodes
            pending = [
                (name, self.value(node, frame))
                for name, node in zip(names, values, strict=False)
                if name != "_"
            ]
            for name, value in pending:
                self.bind(frame, name, value)
            return [*prefix, advanced], None
        if kind == "call":
            function = self.value(statement[1], frame)
            arguments = [self.value(node, frame) for node in statement[2]]
            if isinstance(function, Closure):
                return [*prefix, advanced, self.enter(function, arguments)], None
            self.call(function, arguments)
            return [*prefix, advanced], None
        # A nested loop executes atomically inside its outer loop's body.
        rows, names = self.loop(statement[1], frame)
        for row in rows:
            for name, value in zip(names, row, strict=False):
                self.bind(frame, name, value)
            temporary = replace(frame.function, body=statement[2])
            stack = [Frame(temporary, frame.environment)]
            while stack:
                stack, returned = self.tick(stack)
                if returned is not None and not stack:
                    return prefix, returned
        return [*prefix, advanced], None

    def tick(self, frames):
        self.fuel -= 1
        if self.fuel < 0:
            raise ModelBudgetError
        frame = frames[-1]
        if frame.rows is not None:
            body = frame.function.body[frame.position][2]
            if frame.started and frame.body_position < len(body):
                return self.statement(body[frame.body_position], frames, body=True)
            if frame.index == len(frame.rows):
                return [
                    *frames[:-1],
                    replace(frame, position=frame.position + 1, rows=None),
                ], None
            for name, value in zip(frame.names, frame.rows[frame.index], strict=False):
                self.bind(frame, name, value)
            return [
                *frames[:-1],
                replace(frame, index=frame.index + 1, started=True, body_position=0),
            ], None
        if frame.position == len(frame.function.body):
            return frames[:-1], None
        statement = frame.function.body[frame.position]
        if statement[0] == "for":
            rows, names = self.loop(statement[1], frame)
            return [
                *frames[:-1],
                replace(frame, rows=rows, names=names, index=0, started=False),
            ], None
        return self.statement(statement, frames)


class Machine:
    def __init__(self, program, port):
        self.program = program
        self.port = port
        self.functions = {function.name: function for function in program.functions}
        self.state = State([], [Environment(None, None, {})])
        # Initializers use a synthetic body but retain global lexical bindings.
        for initializer in program.initializers:
            self.attempt(initializer)
        main = self.functions["main"]
        self.state.environments.append(
            Environment(main, 0, dict.fromkeys(main.args, 0))
        )
        self.state.frames = [Frame(main, len(self.state.environments) - 1)]

    @property
    def halted(self):
        return not self.state.frames

    def attempt(self, initializer=None):
        supplied = []
        flushed = 0
        while True:
            attempt = Attempt(self.state, self.functions, tuple(supplied))
            try:
                if initializer is None:
                    frames, _ = attempt.tick(attempt.state.frames)
                    attempt.state.frames = frames
                else:
                    # No function metadata is observed before initialization ends.
                    frame = Frame(None, 0)
                    attempt.statement(initializer, [frame])
            except NeedByte:
                for char in attempt.effects[flushed:]:
                    self.port.write(char)
                    flushed += 1
                supplied.append(self.port.read())
                continue
            except BaseException:
                for char in attempt.effects[flushed:]:
                    self.port.write(char)
                raise
            if initializer is None:
                self.state = attempt.state
            for char in attempt.effects[flushed:]:
                self.port.write(char)
            if initializer is not None:
                self.state = attempt.state
            return

    def step(self):
        if not self.halted:
            self.attempt()

    def parts(self):
        order = [0]
        indices = {0: 0}

        def reference(environment):
            if environment not in indices:
                indices[environment] = len(order)
                order.append(environment)
            return ("reference", (indices[environment],))

        def function(value):
            return ("global", ()) if value is None else ("function", (value.site,))

        def value(item):
            if isinstance(item, Closure):
                return (
                    "closure",
                    (function(item.function), reference(item.environment)),
                )
            if type(item) is int:
                return item
            return ("input" if item == "in" else "output", ())

        for frame in self.state.frames:
            reference(frame.environment)
        frames = []
        for frame in self.state.frames:
            loop = (
                None
                if frame.rows is None
                else (
                    "loop",
                    (
                        tuple(tuple(value(item) for item in row) for row in frame.rows),
                        frame.names,
                        frame.index,
                        frame.started,
                        frame.body_position if frame.started else 0,
                    ),
                )
            )
            frames.append(
                (
                    "frame",
                    (
                        function(frame.function),
                        reference(frame.environment),
                        frame.position,
                        loop,
                    ),
                )
            )
        environments = []
        cursor = 0
        while cursor < len(order):
            scope = self.state.environments[order[cursor]]
            parent = None if scope.parent is None else reference(scope.parent)
            locals_ = frozenset(
                (name, value(item)) for name, item in sorted(scope.values.items())
            )
            environments.append(
                ("environment", (function(scope.function), parent, locals_))
            )
            cursor += 1
        return (
            tuple(frames),
            tuple(environments),
            self.port.position,
            self.state.bits,
            self.state.reads,
        )
