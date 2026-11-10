"""Independent thisthat wire-graph rules and whole-cycle state/IO predictions."""

# Declared node rules; no target transition/parser/state supplies expectations.
# The cycle groups retain one semantic dispatch with local staged IO helpers.
# ruff: noqa: C901, PT018, FBT003, PERF401
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import NamedTuple


class Pointer(NamedTuple):
    """A value travelling from its previous coordinate to its current one."""

    position: tuple
    previous: tuple | None = None
    channel: str = "execution"
    value: int | None = None
    paused: bool = False


class Row(NamedTuple):
    """Copied logical state plus physical IO and successful cycle count."""

    pointers: tuple
    cells: frozenset
    cell_order: tuple
    cursor: int
    stopped: bool
    set_ended: bool
    output: str
    offset: int
    reads: int
    past: int
    character: bool
    newline: bool
    successful: int
    events: tuple
    draws: tuple
    error: str | None

    @property
    def halted(self):
        return self.stopped or not self.pointers

    def parts(self):
        return (
            tuple(tuple(p) for p in self.pointers),
            self.cells,
            self.cursor,
            self.stopped,
            self.offset,
            self.reads,
            self.set_ended,
        )


@dataclass(frozen=True)
class Case:
    """Literal graph/input and existing cycle bound; unfinished runs stay bounded."""

    name: str
    source: tuple
    stdin: str
    cap: int
    finite: bool


# Direction indices are clockwise; connections are symmetric port memberships.
VECTORS = ((1, 0), (0, 1), (-1, 0), (0, -1))
SINGLE = dict(
    zip(
        "─│┌┐└┘├┤┬┴┼",
        ("02", "13", "01", "21", "03", "23", "031", "231", "021", "023", "0231"),
        strict=True,
    )
)
DOUBLE = dict(zip("═║╔╗╚╝╠╣╦╩╬", SINGLE.values(), strict=True))
NODES = frozenset("▣◉◘▲▶▼◀△▷▽◁◯◔◈◇◧⬓◨⬒◹◺◐◑◒◓□■▦")
ARROW = dict(zip("▶▼◀▲▷▽◁△", (0, 1, 2, 3, 0, 1, 2, 3), strict=True))
BLACK = {"◐": 2, "◑": 0, "◒": 1, "◓": 3}
PRIORITY = {**dict.fromkeys("◘◈◹◺", 2), **dict.fromkeys("◇◧⬓◨⬒", 3)}
CONSTANT = {"□": 0, "■": 1, "▦": None}


class InputFaultError(Exception):
    """An invalid physical input character, after its consumption."""


class Model:
    """Direct graph/bistack simulator with buffered print/request microphases."""

    def __init__(self, case, *, choose=None):
        self.case = case
        width = max(map(len, case.source), default=0)
        self.grid = tuple(line.ljust(width) for line in case.source)
        assert all(
            c == " " or c in SINGLE or c in DOUBLE or c in NODES
            for line in self.grid
            for c in line
        )
        self.pointers = tuple(
            Pointer((x, y))
            for y, line in enumerate(self.grid)
            for x, c in enumerate(line)
            if c == "▣"
        )
        assert self.pointers
        self.cells = {}
        self.cursor = 0
        self.stopped = self.set_ended = False
        self.output = ""
        self.offset = self.reads = self.past = self.successful = 0
        self.character = self.newline = False
        self.events, self.draws = [], []
        self.choose = choose if choose is not None else lambda _upper: 0

    def row(self, error=None):
        return Row(
            self.pointers,
            frozenset(self.cells.items()),
            tuple(self.cells),
            self.cursor,
            self.stopped,
            self.set_ended,
            self.output,
            self.offset,
            self.reads,
            self.past,
            self.character,
            self.newline,
            self.successful,
            tuple(self.events),
            tuple(self.draws),
            error,
        )

    def char(self, point):
        x, y = point
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[y]):
            return self.grid[y][x]
        return " "

    def neighbors(self, point, channel):
        glyph = self.char(point)
        wires = SINGLE if channel == "execution" else DOUBLE
        ports = (SINGLE | DOUBLE).get(glyph, "0231" if glyph in NODES else "")
        answer = []
        for digit in ports:
            direction = int(digit)
            dx, dy = VECTORS[direction]
            other = point[0] + dx, point[1] + dy
            target = self.char(other)
            if (target in wires and str((direction + 2) % 4) in wires[target]) or (
                target in NODES and glyph not in NODES
            ):
                answer.append(other)
        return answer

    def incoming(self, pointer):
        if pointer.previous is None:
            return None
        delta = tuple(
            a - b for a, b in zip(pointer.position, pointer.previous, strict=True)
        )
        return VECTORS.index(delta) if delta in VECTORS else None

    def step(self):
        if self.row().halted:
            return
        # Working state commits together; IO effects before a failed request survive.
        cells, cursor, ended = dict(self.cells), self.cursor, self.set_ended
        following, effects = [], []
        flushed, stopping = 0, False

        def flush():
            nonlocal flushed
            for bit in effects[flushed:]:
                self.events.append(("write", bit))
                self.output += str(bit)
                self.newline = True
            flushed = len(effects)

        def read_char():
            flush()
            self.character = True
            self.events.append(("read", None))
            if self.offset == len(self.case.stdin):
                self.past += 1
                return None
            value = ord(self.case.stdin[self.offset])
            self.offset += 1
            self.reads += 1
            self.newline = False
            return value

        def read_bit():
            nonlocal ended
            value = None if ended else read_char()
            while value is not None and value != 10 and chr(value).isspace():
                value = read_char()
            if value == 10:
                ended = True
            if value is None or value == 10:
                return None
            if value not in (48, 49):
                flush()
                raise InputFaultError("thisthat input must be a bit")
            return value - 48

        def exits(pointer, channel):
            return [
                p
                for p in self.neighbors(pointer.position, channel)
                if p != pointer.previous
            ]

        def emit(pointer, places, channel, value=None):
            following.extend(
                Pointer(p, pointer.position, channel, value) for p in places
            )

        def passing(pointer):
            emit(
                pointer, exits(pointer, pointer.channel), pointer.channel, pointer.value
            )

        def sending(pointer, value):
            emit(pointer, exits(pointer, "data"), "data", value)
            emit(pointer, exits(pointer, "execution"), "execution")

        def directed(pointer, direction, channel):
            dx, dy = VECTORS[direction]
            target = pointer.position[0] + dx, pointer.position[1] + dy
            return (
                [target] if target in self.neighbors(pointer.position, channel) else []
            )

        def stack_operation(column, tail, value):
            # Represent each selected axis as its occupied integer positions, then
            # rebuild it independently of persistent native mapping operations.
            fixed, along = (0, 1) if column else (1, 0)
            line = {
                point[along]: bit
                for point, bit in cells.items()
                if point[fixed] == cursor
            }
            original = list(cells)
            old = dict(cells)

            def position_point(position):
                return (cursor, position) if column else (position, cursor)

            result = None
            if value is None:
                if tail:
                    removed = max(line) if line else None
                    result = line.pop(removed) if removed is not None else None
                    order = [
                        point for point in original if point != position_point(removed)
                    ]
                else:
                    result = line.pop(0, None)
                    line = {position - 1: bit for position, bit in line.items()}
                    order = [point for point in original if point[fixed] != cursor]
                    order.extend(position_point(position) for position in sorted(line))
            elif tail:
                position = max(line, default=-1) + 1
                line[position] = value
                order = [*original, position_point(position)]
            else:
                line = {position + 1: bit for position, bit in line.items()}
                line[0] = value
                order = [point for point in original if point[fixed] != cursor]
                order.extend(
                    position_point(position) for position in sorted(line, reverse=True)
                )
            logical = {
                point: bit for point, bit in old.items() if point[fixed] != cursor
            }
            logical.update(
                (position_point(position), bit) for position, bit in line.items()
            )
            cells.clear()
            cells.update((point, logical[point]) for point in order)
            return result

        groups = {}
        for pointer in self.pointers:
            groups.setdefault(pointer.position, []).append(pointer)
        ordered = sorted(
            groups, key=lambda p: (PRIORITY.get(self.char(p), 1), p[1], p[0])
        )
        for point in ordered:
            arrived = groups[point]
            glyph = self.char(point)
            merging = glyph in "◘◈" or (
                glyph in CONSTANT and any(p.channel == "data" for p in arrived)
            )
            if merging:
                if glyph == "◈":
                    if len(arrived) == 1:
                        following.extend(arrived)
                    else:
                        for pointer in arrived:
                            passing(pointer)
                    continue
                for channel in ("execution", "data"):
                    group = [p for p in arrived if p.channel == channel]
                    if not group:
                        continue
                    if glyph in CONSTANT and channel == "execution":
                        for pointer in group:
                            sending(pointer, CONSTANT[glyph])
                        continue
                    chosen = group[0]
                    if glyph == "◘" and len(group) > 1:
                        flush()
                        choice = self.choose(len(group))
                        assert type(choice) is int and 0 <= choice < len(group)
                        self.draws.append((len(group), choice))
                        chosen = group[choice]
                    value = None
                    if channel == "data":
                        ones = sum(p.value == 1 for p in group)
                        value = (
                            int(ones != len(group))
                            if glyph == "◘"
                            else int(ones == 0)
                            if glyph == "□"
                            else int(ones != 0)
                            if glyph == "■"
                            else ones % 2
                        )
                    emit(chosen, exits(chosen, channel), channel, value)
                continue
            for pointer in arrived:
                channel, value = pointer.channel, pointer.value
                if glyph in SINGLE or glyph in DOUBLE:
                    actual = "execution" if glyph in SINGLE else "data"
                    emit(
                        pointer,
                        exits(pointer, actual),
                        actual,
                        value if actual == "data" else None,
                    )
                elif glyph == "▣":
                    emit(pointer, exits(pointer, "execution"), "execution")
                elif glyph == "◉":
                    stopping = True
                elif glyph in ARROW:
                    direction, incoming = ARROW[glyph], self.incoming(pointer)
                    if glyph in "△▷▽◁" and incoming not in (
                        None,
                        direction,
                        (direction + 2) % 4,
                    ):
                        direction = incoming
                    emit(
                        pointer,
                        [
                            p
                            for p in directed(pointer, direction, channel)
                            if p != pointer.previous
                        ],
                        channel,
                        value,
                    )
                elif glyph == "◯":
                    passing(pointer)
                elif glyph == "◔":
                    if pointer.paused:
                        passing(pointer)
                    else:
                        following.append(pointer._replace(paused=True))
                elif glyph == "◇":
                    if channel == "execution":
                        sending(pointer, read_bit())
                    elif value is not None:
                        effects.append(value)
                    elif ended:
                        ended = False
                    else:
                        while read_char() not in (None, 10):
                            pass
                elif glyph in "◧⬓◨⬒":
                    if channel == "execution":
                        sending(
                            pointer, stack_operation(glyph in "⬓⬒", glyph in "◨⬒", None)
                        )
                    else:
                        if value is not None:
                            stack_operation(glyph in "⬓⬒", glyph in "◨⬒", value)
                        emit(pointer, exits(pointer, "execution"), "execution")
                elif glyph in "◹◺":
                    if channel == "data" and value != 1:
                        continue
                    moved = glyph == "◹" or cursor > 0
                    if moved:
                        cursor += 1 if glyph == "◹" else -1
                    if channel == "execution":
                        sending(pointer, int(moved))
                    else:
                        emit(pointer, exits(pointer, "execution"), "execution")
                elif glyph in BLACK:
                    incoming = self.incoming(pointer)
                    if channel == "data":
                        direction = (
                            incoming
                            if value is None
                            else (BLACK[glyph] + (2 if value == 0 else 0)) % 4
                        )
                    elif incoming is None:
                        direction = None
                    elif (incoming + 2) % 4 == (BLACK[glyph] + 2) % 4:
                        direction = incoming
                    elif (incoming + 2) % 4 == BLACK[glyph]:
                        direction = BLACK[glyph]
                    else:
                        direction = (incoming + 1) % 4
                    emit(
                        pointer,
                        []
                        if direction is None
                        else directed(pointer, direction, "execution"),
                        "execution",
                    )
                else:
                    assert glyph in CONSTANT
                    sending(pointer, CONSTANT[glyph])
        self.pointers = () if stopping else tuple(following)
        self.cells, self.cursor, self.stopped, self.set_ended = (
            cells,
            cursor,
            stopping,
            ended,
        )
        flush()
        self.successful += 1


def cases():
    pages = Path(__file__).resolve().parent / "fixtures"
    cat = tuple((pages / "thisthat_cat.txt").read_text().splitlines())
    truth = tuple((pages / "truth-owner-exact.txt").read_text().splitlines())
    kolakoski = tuple((pages / "thisthat_kolakoski.txt").read_text().splitlines())
    result = []
    for length in range(6):
        for values in product("01", repeat=length):
            result.append(
                Case("cat-" + "".join(values), cat, " \t".join(values), 256, True)
            )
    result.extend(
        (
            Case("truth-zero", truth, "0\n", 200, True),
            Case("truth-one", truth, "1\n", 200, False),
            Case("kolakoski", kolakoski, "", 4000, False),
        )
    )
    assert len(result) == 66
    result.append(Case("set-ended-lf", ("▣─◇═◇",), "\n", 32, True))
    return result


def predict(case, *, choose=None):
    machine = Model(case, choose=choose)
    rows = [machine.row()]
    for _ in range(case.cap):
        if case.finite and machine.row().halted:
            break
        try:
            machine.step()
        except InputFaultError:
            rows.append(machine.row("input"))
            break
        rows.append(machine.row())
    if case.finite:
        assert rows[-1].halted, "declared finite source exceeded its unchanged bound"
        for _ in range(3):
            machine.step()
            rows.append(machine.row())
    return machine.grid, rows


def io_values(case, row):
    return {
        "_source": case.stdin,
        "_supplied": case.stdin.count("\n")
        + int(bool(case.stdin) and not case.stdin.endswith("\n")),
        "_offset": row.offset,
        "_line_reads": 0,
        "_character_reads": row.character,
        "_past_end": row.past,
        "_pending": "",
        "_reads": row.reads,
        "_consumed": row.offset,
        "_newline": row.newline,
        "_buffer": (row.output, "\n", len(row.output), None),
    }
