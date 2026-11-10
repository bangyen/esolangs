"""Independent bounded Object disoriented microstates for the exact old IO family."""

# Old terminal/source functions are retained as AST; no target imports occur.
from dataclasses import dataclass
from itertools import product
from typing import NamedTuple


@dataclass(frozen=True)
class Case:
    """Original source-constructor inputs and caller stdin."""

    operations: tuple
    stdin: str = "unused"
    zero: str = "z"


def _expression(value, zero):
    if value == "input":
        return "i"
    if value == "self_copy":
        return "nrsss"
    return "nrpzz" if value else zero


def _source(operations, zero):
    text = []
    for kind, value in operations:
        expression = _expression(value, zero)
        if kind == "write":
            text.append("o" + expression)
        elif kind == "discard":
            text.append(expression)
        else:
            assert kind == "conditional"
            text.append("fi n o" + expression + " rz zz")
    return "dmain." + " ".join(text) + " rzzz"


def _model(operations, stdin):
    unread, pending, output, cursor = ([], [], "", 0)

    def read():
        nonlocal cursor, unread
        if not unread:
            if cursor == len(stdin):
                raise EOFError
            unread = [int(bit) for bit in f"{ord(stdin[cursor]) % 256:08b}"]
            cursor += 1
        return unread.pop(0)

    def terminal(error):
        return (
            error,
            ((tuple(unread), tuple(pending)), error is None, output, cursor, cursor),
        )

    for kind, operand in operations:
        try:
            if kind == "conditional" and read() == 0:
                continue
            value = read() if operand == "input" else int(bool(operand))
        except EOFError:
            return terminal("input")
        if kind != "discard":
            pending.append(value)
            if len(pending) == 8:
                output += chr(int("".join(map(str, pending)), 2))
                pending.clear()
    return terminal(None)


def cases():
    records = []

    def add(_factory, operations, stdin="unused", *, zero="z"):
        records.append(Case(operations, stdin, zero))

    for value in range(256):
        operations = tuple(("write", int(bit)) for bit in f"{value:08b}")
        add(None, operations)
    for count, zero in product(range(10), ("z", "nrzzz")):
        add(None, tuple(("write", i % 2) for i in range(count)), zero=zero)
    add(None, (("write", "self_copy"),) * 8)
    for count, operation, stdin in product(
        (0, 1, 7, 8, 9, 16),
        ("write", "discard", "conditional"),
        ("", "\x00", "ÿ", "\x0fð", "λ\n"),
    ):
        operand = 1 if operation == "conditional" else "input"
        add(None, ((operation, operand),) * count, stdin)
    for first, second in product(("write", "discard", "conditional"), repeat=2):
        add(None, ((first, "input"), (second, "input")) * 8, "¥Zÿ\x00")
    assert len(records) == 376
    return records


class Assembly:
    """Intern known function bodies by first use, an owned representation rule."""

    def __init__(self, case):
        """Compile only the old constructors, not arbitrary language text."""
        self.case = case
        self.codes = []
        assert self.intern((("z", 0), ("ret", 0))) == 0
        assert (
            self.intern(
                (
                    ("ref", "p"),
                    ("z", 0),
                    ("tmp", 0),
                    ("call", 0),
                    ("drop", 0),
                    ("z", 0),
                    ("ret", 0),
                )
            )
            == 1
        )
        main = []
        for kind, value in case.operations:
            if kind == "conditional":
                child = [*self.value(value), ("out", 0), ("z", 0), ("ret", 0)]
                child_id = self.intern(tuple(child))
                main.extend(
                    (
                        ("in", 0),
                        ("tmp", 0),
                        ("z", 0),
                        ("z", 0),
                        ("new", child_id),
                        ("tmp", 0),
                        ("call", 0),
                        ("drop", 0),
                    )
                )
            else:
                main.extend(self.value(value))
                main.append(("out" if kind == "write" else "drop", 0))
        main.extend((("z", 0), ("ret", 0)))
        self.main = self.intern(tuple(main))
        self.boot = self.intern(
            (
                ("z", 0),
                ("z", 0),
                ("new", self.main),
                ("tmp", 0),
                ("z", 0),
                ("tmp", 0),
                ("call", 0),
                ("drop", 0),
                ("z", 0),
                ("ret", 0),
            )
        )
        self.codes = tuple(self.codes)

    def intern(self, code):
        if code not in self.codes:
            self.codes.append(code)
        return self.codes.index(code)

    def value(self, operand):
        if operand == "input":
            return [("in", 0)]
        if operand == "self_copy":
            code = self.intern((("get", "s"), ("ret", 0)))
            return [("get", "s"), ("get", "s"), ("new", code)]
        if operand:
            code = self.intern((("get", "p"), ("ret", 0)))
            return [("z", 0), ("z", 0), ("new", code)]
        if self.case.zero == "z":
            return [("z", 0)]
        assert self.case.zero == "nrzzz"
        return [("z", 0), ("z", 0), ("new", 0)]


@dataclass
class Frame:
    """Independent mutable activation; observations copy every value to tuples."""

    code: int
    pc: int
    owner: object
    parameter: object
    base: int
    pending: object
    stack: list

    def packed(self):
        return (
            self.code,
            self.pc,
            self.owner,
            self.parameter,
            self.base,
            self.pending,
            tuple(self.stack),
        )


class Row(NamedTuple):
    """Independent full state, logical components, complete IO and command count."""

    frames: tuple
    store: tuple
    unread: tuple
    pending: tuple
    output: str
    cursor: int
    reads: int
    past: int
    character: bool
    newline: bool
    successful: int
    error: str | None

    @property
    def halted(self):
        return not self.frames

    def linked(self):
        result = None
        for frame in reversed(self.frames):
            result = (frame, result)
        return result

    def chunks(self):
        # Dense append/truncate store;32 is the persistent library's owned CHUNK.
        return tuple(self.store[i : i + 32] for i in range(0, len(self.store), 32))

    def state(self):
        return self.linked(), self.chunks(), len(self.store), self.unread, self.pending

    def parts(self):
        return (
            self.frames,
            self.store,
            len(self.store),
            self.unread,
            self.pending,
            self.cursor,
        )

    def key(self):
        return (*self.state(), self.cursor)

    def old_terminal(self):
        return (
            self.error,
            (
                (self.unread, self.pending),
                self.halted,
                self.output,
                self.cursor,
                self.cursor,
            ),
        )


class Machine:
    """Execute declared constructor operations using flat cells and mutable calls."""

    def __init__(self, case):
        """Start the declared boot call, with its single zero local cell."""
        self.case, self.program = case, Assembly(case)
        self.frames = [Frame(self.program.boot, 0, 0, 0, 0, None, [])]
        self.store, self.unread, self.pending = [0], [], []
        self.output = ""
        self.cursor = self.reads = self.past = self.successful = 0
        self.character = self.newline = False

    def row(self, error=None):
        return Row(
            tuple(frame.packed() for frame in reversed(self.frames)),
            tuple(self.store),
            tuple(self.unread),
            tuple(self.pending),
            self.output,
            self.cursor,
            self.reads,
            self.past,
            self.character,
            self.newline,
            self.successful,
            error,
        )

    def place(self, frame, name):
        if name == "s":
            return frame.owner
        if name == "p":
            return frame.parameter
        if name == "t":
            return frame.base
        return (frame.owner, 1 if name == "a" else 2)

    def load(self, reference):
        if type(reference) is int:
            return self.store[reference]
        parent, slot = reference
        value = self.load(parent)
        return 0 if value == 0 else value[slot]

    def step(self):
        if not self.frames:
            return
        frame = self.frames[-1]
        instruction, value = self.program.codes[frame.code][frame.pc]
        # The byte is acquired before any opcode or frame commitment.
        if instruction == "in" and not self.unread:
            self.character = True
            if self.cursor == len(self.case.stdin):
                self.past += 1
                raise EOFError
            byte = ord(self.case.stdin[self.cursor]) % 256
            self.cursor += 1
            self.reads += 1
            self.newline = False
            self.unread = [(byte >> bit) & 1 for bit in range(7, -1, -1)]
        frame.pc += 1
        if instruction == "z":
            frame.stack.append(0)
        elif instruction == "in":
            frame.stack.append((1, 0, 0) if self.unread.pop(0) else 0)
        elif instruction == "get":
            frame.stack.append(self.load(self.place(frame, value)))
        elif instruction == "ref":
            frame.stack.append(self.place(frame, value))
        elif instruction == "tmp":
            content = frame.stack.pop()
            frame.stack.append(len(self.store))
            self.store.append(content)
        elif instruction == "new":
            b, a = frame.stack.pop(), frame.stack.pop()
            frame.stack.append(0 if value == 0 and a == 0 and b == 0 else (value, a, b))
        elif instruction == "drop":
            frame.stack.pop()
        elif instruction == "out":
            self.pending.append(int(frame.stack.pop() != 0))
            if len(self.pending) == 8:
                number = 0
                for bit in self.pending:
                    number = number * 2 + bit
                self.output += chr(number)
                self.newline = number != 10
                self.pending.clear()
        elif instruction == "call":
            parameter, owner = frame.stack.pop(), frame.stack.pop()
            held = self.load(owner)
            code = 0 if held == 0 else held[0]
            self.frames.append(
                Frame(code, 0, owner, parameter, len(self.store), None, [])
            )
            self.store.append(0)
        else:
            assert instruction == "ret"
            result = frame.stack.pop()
            assert frame.pending is None  # no c appears in the old source family
            del self.store[frame.base :]
            self.frames.pop()
            if self.frames:
                self.frames[-1].stack.append(result)
        self.successful += 1


def plan(case):
    assert len(case.operations) <= 32
    machine = Machine(case)
    rows = [machine.row()]
    error = None
    for _ in range(512):
        if not machine.frames:
            break
        try:
            machine.step()
        except EOFError:
            error = "input"
            rows.append(machine.row(error))
            break
        rows.append(machine.row())
    else:
        assert not machine.frames, "old bounded case exceeded512 modeled commands"
    if not machine.frames:
        for _ in range(3):
            machine.step()
            rows.append(machine.row())
    assert rows[-1].old_terminal() == _model(case.operations, case.stdin)
    return machine.program, rows


def io_values(case, row):
    return {
        "_source": case.stdin,
        "_supplied": case.stdin.count("\n")
        + int(bool(case.stdin) and not case.stdin.endswith("\n")),
        "_offset": row.cursor,
        "_line_reads": 0,
        "_character_reads": row.character,
        "_past_end": row.past,
        "_pending": "",
        "_reads": row.reads,
        "_consumed": row.cursor,
        "_newline": row.newline,
        "_buffer": (row.output, "\n", len(row.output), None),
    }


def table_labels():
    return (
        *tuple(format(value, f"0{2**n}b") for n in (1, 2) for value in range(2**2**n)),
        "00010111",
        "01101001",
        "11101000",
    )
