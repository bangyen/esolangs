"""Cycle model from the node table, using Unicode wire names and tuple pointers."""

from unicodedata import name

from esolangs.exceptions import HaltError

DIRECTIONS = ((1, 0), (-1, 0), (0, -1), (0, 1))
WIRES = set("─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬")
NODES = set("▣◉◘▲▶▼◀△▷▽◁◯◔◈◇◧⬓◨⬒◹◺◐◑◒◓□■▦")
BLACK = {"◐": (-1, 0), "◑": (1, 0), "◒": (0, 1), "◓": (0, -1)}


def ports(glyph):
    words = set(name(glyph).split())
    result = []
    for vector, word, axis in (
        ((1, 0), "RIGHT", "HORIZONTAL"),
        ((-1, 0), "LEFT", "HORIZONTAL"),
        ((0, -1), "UP", "VERTICAL"),
        ((0, 1), "DOWN", "VERTICAL"),
    ):
        if word in words or axis in words:
            result.append(vector)
    return result


def priority(glyph):
    return 2 if glyph in "◘◈◹◺" else 3 if glyph in "◇◧⬓◨⬒" else 1


class Reference:
    def __init__(self, lines, text="", choice=0):
        width = max(map(len, lines), default=0)
        self.grid = tuple(line.ljust(width) for line in lines)
        self.width = width
        self.pointers = tuple(
            ((x, y), None, 0, None, False)
            for y, line in enumerate(self.grid)
            for x, glyph in enumerate(line)
            if glyph == "▣"
        )
        if not self.pointers:
            raise HaltError("thisthat needs at least one start node")
        unknown = {
            glyph
            for line in self.grid
            for glyph in line
            if glyph != " " and glyph not in WIRES | NODES
        }
        if unknown:
            raise HaltError(f"unsupported thisthat cell: {min(unknown)!r}")
        self.cells = {}
        self.cursor = (0, 0)
        self.stopped = False
        self.text = text
        self.offset = 0
        self.reads = 0
        self.bit_reads = 0
        self.eof_reads = 0
        self.output = ""
        self.choice = choice

    @property
    def halted(self):
        return self.stopped or not self.pointers

    def char(self, point):
        x, y = point
        return (
            self.grid[y][x] if 0 <= y < len(self.grid) and 0 <= x < self.width else " "
        )

    def neighbors(self, point, channel):
        glyph = self.char(point)
        vectors = (
            ports(glyph) if glyph in WIRES else DIRECTIONS if glyph in NODES else ()
        )
        result = []
        for dx, dy in vectors:
            target = (point[0] + dx, point[1] + dy)
            other = self.char(target)
            if other in NODES or (
                other in WIRES
                and int("DOUBLE" in name(other)) == channel
                and (-dx, -dy) in ports(other)
            ):
                result.append(target)
        return result

    def exits(self, pointer, channel):
        return [
            point
            for point in self.neighbors(pointer[0], channel)
            if point != pointer[1]
        ]

    def emit(self, pointer, exits, channel, value=None):
        return [(point, pointer[0], channel, value, False) for point in exits]

    def bit(self):
        while self.offset < len(self.text):
            glyph = self.text[self.offset]
            self.offset += 1
            self.reads += 1
            if glyph.isspace():
                continue
            if glyph not in "01":
                raise HaltError("thisthat input must be a bit")
            self.bit_reads += 1
            return int(glyph)
        self.eof_reads += 1
        return None

    def stack_operation(self, axis, end, value):
        x, y = self.cursor
        dx, dy = (0, 1) if axis == 1 else (-1, 0)
        selected = {
            (point[1] - y if axis else x - point[0]): bit
            for point, bit in self.cells.items()
            if (
                point[0] == x and point[1] > y
                if axis
                else point[1] == y and point[0] < x
            )
        }
        slots = [selected.get(i) for i in range(1, max(selected, default=0) + 1)]
        result = None
        if end == 0:
            if value is None:
                result = slots[0] if slots else None
                slots = slots[1:]
            else:
                slots = [value, *slots]
        elif value is None:
            result = slots.pop() if slots else None
        else:
            slots.append(value)
        self.cells = {
            point: bit
            for point, bit in self.cells.items()
            if not (
                point[0] == x and point[1] > y
                if axis
                else point[1] == y and point[0] < x
            )
        }
        for offset, bit in enumerate(slots, 1):
            if bit is not None:
                self.cells[x + dx * offset, y + dy * offset] = bit
        return result

    def advance(self, pointer):
        point, previous, channel, value, paused = pointer
        glyph = self.char(point)
        if glyph in WIRES:
            channel = int("DOUBLE" in name(glyph))
            return self.emit(
                pointer,
                self.exits(pointer, channel),
                channel,
                value if channel else None,
            )
        if glyph == "▣":
            return self.emit(pointer, self.exits(pointer, 0), 0)
        if glyph == "◉":
            self.stopped = True
            return []
        incoming = (
            None
            if previous is None
            else (point[0] - previous[0], point[1] - previous[1])
        )
        if glyph in "▲▶▼◀△▷▽◁":
            direction = DIRECTIONS["▶◀▲▼▷◁△▽".index(glyph) % 4]
            if (
                glyph in "△▷▽◁"
                and incoming is not None
                and incoming not in (direction, (-direction[0], -direction[1]))
            ):
                return []
            target = (point[0] + direction[0], point[1] + direction[1])
            return self.emit(
                pointer,
                [target] if target in self.neighbors(point, channel) else [],
                channel,
                value,
            )
        if glyph == "◯":
            return self.emit(pointer, self.exits(pointer, channel), channel, value)
        if glyph == "◔":
            return (
                self.emit(pointer, self.exits(pointer, channel), channel, value)
                if paused
                else [(point, previous, channel, value, True)]
            )
        if glyph == "◇":
            if channel == 0:
                return self.emit(pointer, self.exits(pointer, 1), 1, self.bit())
            if value is not None:
                self.output += str(value)
            return []
        if glyph in "◧⬓◨⬒":
            axis = int(glyph in "⬓⬒")
            end = int(glyph in "◨⬒")
            if channel == 0:
                return self.emit(
                    pointer,
                    self.exits(pointer, 1),
                    1,
                    self.stack_operation(axis, end, None),
                )
            if value is not None:
                self.stack_operation(axis, end, value)
            return self.emit(pointer, self.exits(pointer, 0), 0)
        if glyph in "◹◺":
            if channel == 1 and value != 1:
                return []
            delta = -1 if glyph == "◹" else 1
            target = (self.cursor[0] + delta, self.cursor[1] + delta)
            moved = target not in self.cells
            if moved:
                self.cursor = target
            return self.emit(
                pointer,
                self.exits(pointer, 1 - channel),
                1 - channel,
                int(moved) if channel == 0 else None,
            )
        if glyph in BLACK:
            black = BLACK[glyph]
            white = (-black[0], -black[1])
            side = None if incoming is None else (-incoming[0], -incoming[1])
            if channel == 1:
                direction = (
                    incoming if value is None else white if value == 0 else black
                )
            elif incoming is None:
                direction = None
            elif side == white:
                direction = incoming
            elif side == black:
                direction = black
            else:
                direction = (-incoming[1], incoming[0])
            if direction is None:
                return []
            target = (point[0] + direction[0], point[1] + direction[1])
            return self.emit(
                pointer, [target] if target in self.neighbors(point, 0) else [], 0
            )
        if glyph in "□■▦":
            return self.emit(
                pointer, self.exits(pointer, 1), 1, {"□": 0, "■": 1, "▦": None}[glyph]
            )
        raise HaltError(f"unsupported thisthat cell: {glyph!r}")

    def merge(self, glyph, arrived):
        if glyph == "◈":
            return (
                arrived
                if len(arrived) < 2
                else [
                    _emitted
                    for pointer in arrived
                    for _emitted in self.emit(
                        pointer, self.exits(pointer, pointer[2]), pointer[2], pointer[3]
                    )
                ]
            )
        following = []
        for channel in (0, 1):
            group = [pointer for pointer in arrived if pointer[2] == channel]
            if not group:
                continue
            if channel == 0 and glyph != "◘":
                following += [
                    _emitted
                    for pointer in group
                    for _emitted in self.emit(
                        pointer,
                        self.exits(pointer, 1),
                        1,
                        {"□": 0, "■": 1, "▦": None}[glyph],
                    )
                ]
                continue
            chosen = group[self.choice % len(group)] if glyph == "◘" else group[0]
            bits = [pointer[3] == 1 for pointer in group]
            value = (
                None
                if channel == 0
                else (
                    1 - int(all(bits))
                    if glyph == "◘"
                    else 1 - int(any(bits))
                    if glyph == "□"
                    else int(any(bits))
                    if glyph == "■"
                    else sum(bits) % 2
                )
            )
            following += self.emit(chosen, self.exits(chosen, channel), channel, value)
        return following

    def step(self):
        if self.halted:
            return
        positions = sorted(
            {pointer[0] for pointer in self.pointers},
            key=lambda point: (priority(self.char(point)), point[1], point[0]),
        )
        following = []
        for point in positions:
            arrived = [pointer for pointer in self.pointers if pointer[0] == point]
            glyph = self.char(point)
            if glyph in "◘◈" or (
                glyph in "□■▦" and any(pointer[2] == 1 for pointer in arrived)
            ):
                following += self.merge(glyph, arrived)
            else:
                for pointer in arrived:
                    following += self.advance(pointer)
            if self.stopped:
                following = []
                break
        self.pointers = tuple(following)
