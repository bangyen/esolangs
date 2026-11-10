"""Independent old511 one-row Streetcode predictor, unchanged cap48."""

from itertools import product
from typing import NamedTuple


class Case(NamedTuple):
    """One unchanged wall-free row and literal input."""

    source: str
    stdin: str


class Row(NamedTuple):
    """Full row state plus independently replayed IO flags."""

    state: tuple
    halted: bool
    output: str
    cursor: int
    progress: int
    character_reads: bool
    past_end: int
    newline: bool


def _model(source, stdin):
    pc, direction, pointer, cursor, reads = 0, (1 if len(source) > 1 else 0), 0, 0, 0
    cells, done, output, trace = {}, False, "", []

    def row():
        heading = "E" if direction == 1 else "W" if direction == -1 else "S"
        state = pc, heading, pointer, tuple(sorted(cells.items())), reads
        return state, done, output, cursor, cursor

    for tick in range(49):
        trace.append(row())
        if done:
            return None, trace + [row()] * 3
        if tick == 48:
            break
        command = source[pc]
        if command == ";":
            done = True
            continue
        if command == "U" or (command == "_" and pointer == 0):
            return "halt", [*trace, row()]
        value = cells.get(pointer, 0)
        if command == "O" and not 0 <= value <= 0x10FFFF:
            return "halt", [*trace, row()]
        if command == "I":
            if cursor == len(stdin):
                return "input", [*trace, row()]
            cells[pointer] = ord(stdin[cursor])
            reads, cursor = reads + 1, cursor + 1
        elif command in "^~":
            cells[pointer] = value + (1 if command == "^" else -1)
        elif command == "=":
            pointer += 1
        elif command == "_":
            pointer -= 1
        elif command == "O":
            output += chr(value)
        if len(source) == 1:
            done = True
        else:
            if not 0 <= pc + direction < len(source):
                direction = -direction
            pc += direction
    return None, trace


def cases():
    """Retain all511 old natural source/input pairs in order."""
    result = []
    for first, second in product("^~=_IOU; abc?><", repeat=2):
        result.append(Case("C" + first + second + ";", "Aλ"))
    for first, second, third in product(("^", "~", "=", "_", "O", "a"), repeat=3):
        result.append(Case("C" + first + second + third, "unused"))
    for source in (
        "",
        ";",
        "^=^_O;",
        "^^^^O;",
        "~^O;",
        "=~O;",
        "===___;",
        "U;",
        "I=I_OO;",
        "IOIOIO;",
        "I~O;",
        "I^O;",
        "IO",
        "I^O^;",
    ):
        for stdin in ("", "AB", "λ\n", "\0", chr(0x10FFFF)):
            result.append(Case("C" + source, stdin))  # noqa: PERF401 -- Preserve old literal iteration order.
    assert len(result) == 511
    return result


def predict(case):
    """Enrich the unchanged old trace with physical IO phase flags."""
    error, old = _model(case.source, case.stdin)
    result = []
    character_reads, newline = False, False
    for index, (state, halted, output, cursor, progress) in enumerate(old):
        failed = index == len(old) - 1 and error is not None
        if index and not old[index - 1][1]:
            command = case.source[old[index - 1][0][0]]
            if command == "I":
                character_reads = True
                if not failed:
                    newline = False
            elif command == "O" and not failed:
                newline = output[-1] != "\n"
        result.append(
            Row(
                state,
                halted,
                output,
                cursor,
                progress,
                character_reads,
                int(failed and error == "input"),
                newline,
            )
        )
    return error, result


def parts(row):
    """Map the admitted one-row state to all six semantic components."""
    pc, heading, pointer, cells, reads = row.state
    return (
        (0, pc, heading, (None, None, 0)),
        pointer,
        frozenset(cells),
        row.cursor,
        row.halted,
        reads,
    )


def width(value):
    """Count semantic payload with signed integer and character widths."""
    if value is None:
        return 0
    if type(value) is bool:
        return 1
    if type(value) is int:
        return max(1, abs(value).bit_length()) + (value < 0)
    if type(value) is str:
        return 8 * len(value)
    assert type(value) in (tuple, frozenset)
    return sum(width(child) for child in value)


def witness():
    """Predict the natural35bit all-six-written trajectory."""
    case = Case("CI=IO;", "AB")
    error, rows = predict(case)
    assert error is None
    assert rows[-1].halted is True
    assert rows[-1].output == "B"
    captures = [parts(row) for row in rows]
    initial = captures[0]
    peaks = [max(width(saved[field]) for saved in captures) for field in range(6)]
    written = [
        any(saved[field] != initial[field] for saved in captures) for field in range(6)
    ]
    assert peaks == [13, 1, 16, 2, 1, 2]
    assert written == [True] * 6
    assert sum(peaks) == 35
    return case, rows
