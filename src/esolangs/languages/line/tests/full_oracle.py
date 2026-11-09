"""Independent Line transition design; fixture geometry mappings remain unproved.

No native imports. This is not a complete PNG oracle or acceptance candidate.
A named graph must be justified from its drawing before canonical_graph runs.
"""

import re
from collections import deque
from typing import NamedTuple


class Stroke(NamedTuple):
    """A source-derived stroke and its drawn successor links."""

    name: str
    operations: tuple[tuple[str, int], ...]
    positions: tuple[tuple[int, int], ...]
    end: tuple[int, int]
    zero: str | None = None
    nonzero: str | None = None
    merge: str | None = None


class Frame(NamedTuple):
    """Independent readonly metadata, never constructed from a native frame."""

    operations: tuple[tuple[str, int], ...]
    positions: tuple[tuple[int, int], ...]
    end: tuple[int, int]
    zero: int | None
    nonzero: int | None
    merge: int | None


class State(NamedTuple):
    """Logical control plus every visited tape entry, including written zeros."""

    node: int | None = 0
    instruction: int = 0
    pointer: int = 0
    visited: tuple[tuple[int, int], ...] = ()


class InputEndError(Exception):
    """A real attempted token read reached EOF."""


class BadTokenError(Exception):
    """A consumed token failed the declared ASCII decimal grammar."""


def canonical_graph(strokes, entry):
    """Number justified named strokes breadth first, zero/nonzero/merge in order."""
    declared = {stroke.name: stroke for stroke in strokes}
    assert len(declared) == len(strokes)
    assert entry in declared
    pending, names = deque([entry]), [entry]
    numbers = {entry: 0}
    while pending:
        name = pending.popleft()
        stroke = declared[name]
        assert len(stroke.operations) == len(stroke.positions)
        for opcode, count in stroke.operations:
            assert opcode in ("+", "-", "<", ">", "i", "o")
            assert type(count) is int
            assert count >= 0
        for child in (stroke.zero, stroke.nonzero, stroke.merge):
            if child is not None:
                assert child in declared
                if child not in numbers:
                    numbers[child] = len(names)
                    names.append(child)
                    pending.append(child)
    assert set(names) == set(declared), "unreachable or unproved source stroke"
    return tuple(
        Frame(
            declared[name].operations,
            declared[name].positions,
            declared[name].end,
            numbers.get(declared[name].zero),
            numbers.get(declared[name].nonzero),
            numbers.get(declared[name].merge),
        )
        for name in names
    )


class NumericInput:
    """Token framing and counters independent of the production IO adapter."""

    def __init__(self, text):
        """Start with no physical input attempt or output newline."""
        self.text, self.cursor, self.reads, self.past = text, 0, 0, 0
        self.character = self.newline = False

    def read(self):
        """Consume a numeric token before any control/tape commit."""
        self.character = True
        while self.cursor < len(self.text) and self.text[self.cursor].isspace():
            self.cursor += 1
        if self.cursor == len(self.text):
            self.past += 1
            raise InputEndError
        start = self.cursor
        while self.cursor < len(self.text) and not self.text[self.cursor].isspace():
            self.cursor += 1
        token = self.text[start : self.cursor]
        self.reads += 1
        self.newline = False
        if re.fullmatch(r"[+-]?[0-9]+", token) is None:
            raise BadTokenError
        negative = token.startswith("-")
        digits = token[1:] if token[0] in "+-" else token
        value = 0
        for char in digits:
            value = 10 * value + ord(char) - ord("0")
        value = -value if negative else value
        assert 0 <= value <= 5, "original fixture operand domain remains 0..5"
        return value


def needs_number(state, frames):
    """Whether this justified operation consumes a token."""
    return (
        state.node is not None
        and state.instruction < len(frames[state.node].operations)
        and frames[state.node].operations[state.instruction][0] == "i"
    )


def transition(state, frames, number=None):
    """Apply one operation or one drawn branch/merge/exit boundary."""
    node, at, pointer, tape = state
    if node is None:
        return state, None
    frame, cells = frames[node], dict(tape)
    value = cells.get(pointer, 0)
    if at == len(frame.operations):
        if frame.zero is None and frame.nonzero is None:
            destination = frame.merge
        else:
            cells[pointer] = value
            destination = frame.zero if value == 0 else frame.nonzero
        return State(destination, 0, pointer, tuple(sorted(cells.items()))), None
    opcode, count = frame.operations[at]
    output = None
    if opcode == "+":
        cells[pointer] = value + count
    elif opcode == "-":
        cells[pointer] = value - count
    elif opcode == ">":
        pointer += 1
    elif opcode == "<":
        pointer -= 1
    elif opcode == "i":
        assert type(number) is int
        cells[pointer] = number
    else:
        assert opcode == "o"
        cells[pointer] = value
        output = value
    return State(node, at + 1, pointer, tuple(sorted(cells.items()))), output


def capture(state, frames, port, output):
    """Separate raw tape, nonzero capture, cycle key and memory/IP views."""
    node, at, pointer, tape = state
    nonzero = tuple((key, value) for key, value in tape if value)
    workspace = node, at, pointer, frozenset(nonzero), port.cursor
    cycle = node, at, pointer, nonzero, port.cursor
    ip = (
        None
        if node is None
        else (
            frames[node].positions[at]
            if at < len(frames[node].operations)
            else frames[node].end
        )
    )
    cells = dict(tape)
    memory = tuple(
        cells.get(i, 0) for i in range(min(cells, default=0), max(cells, default=0) + 1)
    )
    return {
        "raw": state,
        "workspace": workspace,
        "cycle": cycle,
        "ip": ip,
        "memory": memory,
        "halted": node is None,
        "output": output,
        "position": port.cursor,
        "reads": port.reads,
        "past_end": port.past,
        "character_reads": port.character,
        "newline": port.newline,
    }


def model(frames, stdin, cap=1000):
    """Retain all bounded ordinary boundaries; EOF/token errors precede transition."""
    state, port, output, rows = State(), NumericInput(stdin), "", []
    for tick in range(cap + 1):
        rows.append(capture(state, frames, port, output))
        if state.node is None:
            return None, rows + [capture(state, frames, port, output) for _ in range(3)]
        if tick == cap:
            return None, rows
        try:
            number = port.read() if needs_number(state, frames) else None
        except (InputEndError, BadTokenError) as error:
            rows.append(capture(state, frames, port, output))
            return ("input" if isinstance(error, InputEndError) else "argument"), rows
        state, emitted = transition(state, frames, number)
        # A real physical output refusal belongs AFTER this state assignment.
        # The later fault-history driver must capture it here, never roll back.
        if emitted is not None:
            text = str(emitted)  # Admitted operands0..5 keep output small.
            output += text
            port.newline = True
    raise AssertionError("bounded trace did not finish")


def writer_refusal_history(frames, stdin):
    """Predict a first physical numeric-write refusal after its state commit."""
    error, ordinary = model(frames, stdin)
    assert error is None
    at = next(
        i
        for i in range(1, len(ordinary))
        if ordinary[i]["output"] != ordinary[i - 1]["output"]
    )
    text = ordinary[at]["output"][len(ordinary[at - 1]["output"]) :]
    assert text
    histories = []
    for prefix in ("", text[:1]):
        rows = []
        output = ""
        newline = False
        for index, original in enumerate(ordinary):
            row = dict(original)
            if index < at:
                output, newline = row["output"], row["newline"]
            elif index == at:
                output += prefix
                row["raised"] = "physical ValueError after state commit"
            else:
                previous = ordinary[index - 1]
                if row["reads"] > previous["reads"]:
                    newline = False
                appended = original["output"][len(previous["output"]) :]
                if appended:
                    output += appended
                    newline = True
            row["output"], row["newline"] = output, newline
            rows.append(row)
        histories.append(tuple(rows))
    return tuple(histories)


def provider_refusal_history(frames, stdin):
    """Insert a before-delegate numeric-reader refusal, then retry unchanged input."""
    error, ordinary = model(frames, stdin)
    at = next(
        i
        for i in range(1, len(ordinary))
        if ordinary[i]["reads"] > ordinary[i - 1]["reads"]
        or ordinary[i]["past_end"] > ordinary[i - 1]["past_end"]
    )
    failed = {**ordinary[at - 1], "raised": "provider ValueError before delegate"}
    return error, (*ordinary[:at], failed, *ordinary[at:])


# Independent V4 ink paths, cropped by (top,left)=(35,17)/(51,25).
GRAPHS = {
    "addition": canonical_graph(
        (
            Stroke(
                "read",
                (("i", 1), (">", 1), ("i", 1)),
                ((202, 142), (142, 142), (102, 142)),
                (22, 142),
                "exit",
                "transfer",
                None,
            ),
            Stroke(
                "exit",
                (("<", 1), ("o", 1)),
                ((22, 162), (22, 202)),
                (22, 261),
                None,
                None,
                None,
            ),
            Stroke(
                "transfer",
                (("-", 1), ("<", 1), ("+", 1), (">", 1)),
                ((22, 102), (42, 62), (62, 22), (102, 22)),
                (42, 142),
                None,
                None,
                "resume-test",
            ),
            Stroke("resume-test", (), (), (22, 142), "exit", "transfer", None),
        ),
        "read",
    ),
    "multiplication": canonical_graph(
        (
            Stroke(
                "read",
                (("i", 1), (">", 1), ("i", 1), ("<", 1)),
                ((382, 362), (322, 362), (282, 362), (222, 362)),
                (142, 362),
                "exit",
                "multiplier-test",
                None,
            ),
            Stroke(
                "exit",
                ((">", 1), (">", 1), ("o", 1)),
                ((122, 402), (102, 402), (62, 402)),
                (3, 402),
                None,
                None,
                None,
            ),
            Stroke(
                "multiplier-test",
                ((">", 1),),
                ((142, 262),),
                (142, 182),
                "scratch-test",
                "transfer",
                None,
            ),
            Stroke(
                "scratch-test",
                ((">", 1), (">", 1)),
                ((102, 182), (82, 182)),
                (22, 182),
                "outer-decrement",
                "restore",
                None,
            ),
            Stroke(
                "transfer",
                ((">", 1), ("+", 1), (">", 1), ("+", 1), ("<", 1), ("<", 1), ("-", 1)),
                (
                    (162, 182),
                    (202, 182),
                    (242, 162),
                    (282, 162),
                    (322, 142),
                    (342, 142),
                    (402, 162),
                ),
                (142, 202),
                None,
                None,
                "resume-multiplier",
            ),
            Stroke(
                "outer-decrement",
                (("<", 1), ("<", 1), ("<", 1), ("-", 1)),
                ((22, 202), (22, 222), (21, 243), (22, 282)),
                (162, 362),
                None,
                None,
                "resume-outer",
            ),
            Stroke(
                "restore",
                (("-", 1), ("<", 1), ("<", 1), ("+", 1), (">", 1), (">", 1)),
                ((22, 142), (42, 102), (42, 82), (42, 42), (102, 22), (102, 42)),
                (42, 182),
                None,
                None,
                "resume-scratch",
            ),
            Stroke(
                "resume-multiplier",
                (),
                (),
                (142, 182),
                "scratch-test",
                "transfer",
                None,
            ),
            Stroke("resume-outer", (), (), (142, 362), "exit", "multiplier-test", None),
            Stroke(
                "resume-scratch", (), (), (22, 182), "outer-decrement", "restore", None
            ),
        ),
        "read",
    ),
}
