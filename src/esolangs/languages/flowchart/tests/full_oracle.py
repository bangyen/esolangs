"""Independent declared-layout semantics; no native parsing or state helpers."""

from typing import NamedTuple

# Clockwise order gives heading-relative choices without native turn helpers.
_DIRECTIONS = ((0, 1), (1, 0), (0, -1), (-1, 0))
_ARMS = {
    "─": (0, 2),
    "│": (1, 3),
    "┌": (0, 1),
    "┐": (1, 2),
    "└": (0, 3),
    "┘": (2, 3),
    "┬": (0, 1, 2),
    "┴": (0, 2, 3),
    "├": (0, 1, 3),
    "┤": (1, 2, 3),
    "┼": (0, 1, 2, 3),
}
_SPELL = {
    "fork": "( )",
    "end": "(( ))",
    "toggle": "[ ]",
    "zero": "{ ]",
    "one": "[ }",
    "empty": "{ }",
    "switch": "< >",
    "read": "/ /",
    "write": "\\ \\",
    "push_top": "\\[ ]/",
    "push_bottom": "/[ ]\\",
    "pop_top": "\\{ }/",
    "pop_bottom": "/{ }\\",
    "left": "< ]",
    "right": "[ >",
}


class _Box(NamedTuple):
    row: int
    column: int
    kind: str


class _Case(NamedTuple):
    rows: tuple[str, ...]
    boxes: tuple[_Box, ...]
    rails: tuple[tuple[int, int, str], ...]
    stdin: str


class _Pointer(NamedTuple):
    row: int
    column: int
    heading: tuple[int, int]
    register: int | None
    deque: int
    done: bool
    previous: tuple[int, int] | None
    memory: frozenset


class _Run(NamedTuple):
    pointers: tuple[_Pointer, ...]
    deques: frozenset
    outgoing: int
    used: int


class _RefusalError(Exception):
    """A declared before-delegate read or physical write refusal."""


def _layout(boxes, rails, stdin=""):
    """Render an independently declared layout; never recognize source nodes."""
    cells = {}
    for box in boxes:
        for delta, character in enumerate(_SPELL[box.kind]):
            key = box.row, box.column + delta
            assert key not in cells
            cells[key] = character
    for row, column, character in rails:
        assert character in _ARMS
        assert (row, column) not in cells
        cells[row, column] = character
    height = max(row for row, _ in cells) + 1
    width = max(column for _, column in cells) + 1
    rows = tuple(
        "".join(cells.get((row, column), " ") for column in range(width))
        for row in range(height)
    )
    return _Case(rows, tuple(boxes), tuple(rails), stdin)


def _straight(kinds, stdin=""):
    boxes, rails = [_Box(0, 0, "fork")], []
    column = 3
    for kind in (*kinds, "end"):
        rails.append((0, column, "─"))
        column += 1
        boxes.append(_Box(0, column, kind))
        column += len(_SPELL[kind])
    return _layout(boxes, rails, stdin)


def _cases():
    cases = []
    for width in range(1, 18):
        for data in ("", "A", "AB", "AC", "Ł", "\0", "U", "ª", "ÿ"):
            case = _straight(("read", "write") * width, data)
            body = "─".join(["/ /─\\ \\"] * width)
            assert case.rows == (f"( )─{body}─(( ))",)
            cases.append(case)
    assert len(cases) == 153
    return cases


class _Port:
    def __init__(self, text):
        self.text = text
        self.cursor = self.reads = self.past = 0
        self.character = self.newline = False
        self.output = ""
        self.events = []
        self.read_attempts = self.write_attempts = 0
        self.refuse_read = self.refuse_write = None
        self.prefix = 0

    def read(self):
        self.read_attempts += 1
        if self.read_attempts == self.refuse_read:
            self.events.append(("refuse_read", self.read_attempts))
            raise _RefusalError("read")
        self.character = True
        if self.cursor == len(self.text):
            self.past += 1
            self.events.append(("eof",))
            return None
        value = ord(self.text[self.cursor])
        self.cursor += 1
        self.reads += 1
        self.newline = False
        self.events.append(("read", value))
        return value

    def write(self, value):
        self.write_attempts += 1
        if self.write_attempts == self.refuse_write:
            self.output += chr(value)[: self.prefix]
            self.events.append(("refuse_write", value, self.prefix))
            raise _RefusalError("write")
        self.output += chr(value)
        self.newline = value != 10
        self.events.append(("write", value))


class _Model:
    def __init__(self, case):
        self.case, self.port = case, _Port(case.stdin)
        self.node_at = {}
        self.rails = {(r, c): char for r, c, char in case.rails}
        for box in case.boxes:
            for delta in range(len(_SPELL[box.kind])):
                self.node_at[box.row, box.column + delta] = box
        start = min(
            (b for b in case.boxes if b.kind == "fork"), key=lambda b: (b.column, b.row)
        )
        steps = self.exits(start, None)
        assert steps
        steps = self.fork_order(steps, (0, 1))
        self.run = _Run(
            tuple(
                _Pointer(
                    r,
                    c,
                    d,
                    None,
                    0,
                    done=False,
                    previous=(start.row, start.column),
                    memory=frozenset(),
                )
                for r, c, d in steps
            ),
            frozenset(),
            0,
            0,
        )
        self.input_reads = self.incoming = self.remaining = 0

    def exits(self, box, previous):
        found = []
        for column in range(box.column, box.column + len(_SPELL[box.kind])):
            for index, (dr, dc) in enumerate(_DIRECTIONS):
                target = box.row + dr, column + dc
                if target == previous or target not in self.rails:
                    continue
                if (index + 2) % 4 in _ARMS[self.rails[target]]:
                    found.append((*target, (dr, dc)))
        return found

    @staticmethod
    def preference(heading):
        index = _DIRECTIONS.index(heading)
        return tuple(_DIRECTIONS[(index + delta) % 4] for delta in (0, 1, -1, 2))

    def fork_order(self, exits, heading):
        ordered = sorted(exits, key=lambda step: step[:2])
        own = min(ordered, key=lambda step: self.preference(heading).index(step[2]))
        return [own, *(step for step in ordered if step != own)]

    def anchor(self, pointer):
        box = self.node_at.get((pointer.row, pointer.column))
        return (box.row, box.column) if box else (pointer.row, pointer.column)

    def moved(self, pointer, target, heading):
        memory = dict(pointer.memory)
        memory[self.anchor(pointer)] = heading
        return pointer._replace(
            row=target[0],
            column=target[1],
            heading=heading,
            previous=(pointer.row, pointer.column),
            memory=frozenset(memory.items()),
        )

    def remembered(self, pointer, allowed):
        remembered = dict(pointer.memory).get(self.anchor(pointer))
        opposite = (-pointer.heading[0], -pointer.heading[1])
        return remembered if remembered in allowed and remembered != opposite else None

    def ride(self, pointer):
        seen = set()
        while not pointer.done and (pointer.row, pointer.column) not in self.node_at:
            key = pointer.row, pointer.column, pointer.heading
            if key in seen:
                break
            seen.add(key)
            heading_index = _DIRECTIONS.index(pointer.heading)
            allowed = [
                _DIRECTIONS[index]
                for index in _ARMS[self.rails[pointer.row, pointer.column]]
                if index != (heading_index + 2) % 4
            ]
            if len(allowed) > 1:
                recalled = self.remembered(pointer, allowed)
                if recalled is not None:
                    allowed = [recalled]
                elif pointer.heading in allowed:
                    allowed = [pointer.heading]
            heading = next(
                d for d in self.preference(pointer.heading)[:3] if d in allowed
            )
            target = pointer.row + heading[0], pointer.column + heading[1]
            if target not in self.node_at and (
                target not in self.rails
                or _DIRECTIONS.index((-heading[0], -heading[1]))
                not in _ARMS[self.rails[target]]
            ):
                # Native movement records the selected exit even when its rail ends.
                memory = dict(pointer.memory)
                memory[self.anchor(pointer)] = heading
                pointer = pointer._replace(memory=frozenset(memory.items()), done=True)
            else:
                pointer = self.moved(pointer, target, heading)
        return pointer

    @property
    def halted(self):
        return all(p.done for p in self.run.pointers)

    def row(self):
        parts = (
            tuple(tuple(p) for p in self.run.pointers),
            self.run.deques,
            self.port.cursor,
            self.input_reads,
            self.incoming,
            self.remaining,
            self.run.outgoing,
            self.run.used,
        )
        return parts, self.halted, self.port.output, self.port.cursor, self.port.cursor

    def io(self):
        return self.port.reads, self.port.past, self.port.character, self.port.newline

    def operation(self, pointer, kind, deques, read, outgoing, used, pending):
        register, cursor = pointer.register, pointer.deque
        if kind == "toggle":
            register = 1 if register is None else 1 - register
        elif kind in ("zero", "one", "empty"):
            register = {"zero": 0, "one": 1, "empty": None}[kind]
        elif kind == "read":
            register = read()
        elif kind == "write":
            outgoing += (register or 0) * (2**used)
            used += 1
            if used == 8:
                pending.append(outgoing)
                outgoing = used = 0
        elif kind.startswith("push_"):
            values = deques.get(cursor, ())
            deques[cursor] = (
                (*values, register) if kind == "push_top" else (register, *values)
            )
        elif kind.startswith("pop_"):
            values = deques.get(cursor, ())
            register = (
                (values[-1] if kind == "pop_top" else values[0]) if values else None
            )
            deques[cursor] = values[:-1] if kind == "pop_top" else values[1:]
        elif kind in ("left", "right"):
            cursor += 1 if kind == "right" else -1
        else:
            assert kind == "switch"
        return pointer._replace(register=register, deque=cursor), outgoing, used

    def step(self):
        if self.halted:
            return
        pointers = [self.ride(p) if not p.done else p for p in self.run.pointers]
        deques = dict(self.run.deques)
        outgoing, used = self.run.outgoing, self.run.used
        pending, flushed = [], 0

        def flush():
            nonlocal flushed
            while flushed < len(pending):
                self.port.write(pending[flushed])
                flushed += 1

        def read():
            flush()
            if self.remaining == 0:
                value = self.port.read()
                if value is None:
                    return None
                self.input_reads += 1
                self.incoming, self.remaining = value % 256, 8
            result = self.incoming % 2
            self.incoming //= 2
            self.remaining -= 1
            return result

        live = [
            i
            for i, p in enumerate(pointers)
            if not p.done and (p.row, p.column) in self.node_at
        ]
        live.sort(
            key=lambda i: (
                pointers[i].row,
                self.node_at[pointers[i].row, pointers[i].column].column,
                i,
            )
        )
        for index in live:
            pointer = pointers[index]
            box = self.node_at[pointer.row, pointer.column]
            kind = box.kind
            if kind == "end":
                pointers[index] = pointer._replace(done=True)
                continue
            exits = self.exits(box, pointer.previous)
            assert exits
            if kind == "fork":
                ordered = self.fork_order(exits, pointer.heading)
                for r, c, d in ordered[1:]:
                    pointers.append(
                        _Pointer(
                            r,
                            c,
                            d,
                            pointer.register,
                            pointer.deque,
                            done=False,
                            previous=(pointer.row, pointer.column),
                            memory=pointer.memory,
                        )
                    )
                selected = ordered[0]
            else:
                pointer, outgoing, used = self.operation(
                    pointer, kind, deques, read, outgoing, used, pending
                )
                order = sorted(
                    exits,
                    key=lambda step: self.preference(pointer.heading).index(step[2]),
                )
                preferred = None
                if kind == "switch":
                    delta = -1 if pointer.register == 1 else 1
                    preferred = (
                        pointer.heading
                        if pointer.register is None
                        else _DIRECTIONS[
                            (_DIRECTIONS.index(pointer.heading) + delta) % 4
                        ]
                    )
                    if preferred not in [step[2] for step in order]:
                        preferred = pointer.heading
                elif len(order) > 1:
                    preferred = self.remembered(pointer, [step[2] for step in order])
                selected = next(
                    (step for step in order if step[2] == preferred), order[0]
                )
            pointers[index] = self.moved(pointer, selected[:2], selected[2])
        if used and all(p.done for p in pointers):
            pending.append(outgoing)
            outgoing = used = 0
        self.run = _Run(
            tuple(pointers),
            frozenset((k, tuple(v)) for k, v in deques.items() if v),
            outgoing,
            used,
        )
        flush()


def _model(case, cap=64):
    model, rows, ios = _Model(case), [], []
    for tick in range(cap + 1):
        rows.append(model.row())
        ios.append(model.io())
        if model.halted:
            return rows + [model.row()] * 3, ios + [model.io()] * 3
        if tick < cap:
            model.step()
    return rows, ios


def _fork_case():
    return _layout(
        (
            _Box(0, 0, "fork"),
            _Box(0, 4, "one"),
            _Box(0, 8, "one"),
            _Box(0, 12, "fork"),
            _Box(0, 16, "write"),
            _Box(0, 20, "end"),
            _Box(2, 12, "write"),
            _Box(4, 11, "end"),
        ),
        (
            (0, 3, "─"),
            (0, 7, "─"),
            (0, 11, "─"),
            (0, 15, "─"),
            (0, 19, "─"),
            (1, 13, "│"),
            (3, 13, "│"),
        ),
    )


def _reentry_case():
    # Two initial paths meet the fork from different directions. The surviving
    # path re-enters both forks; each round also retains another stopped clone.
    return _layout(
        (_Box(0, 0, "fork"), _Box(0, 4, "fork"), _Box(0, 8, "end")),
        (
            (0, 3, "─"),
            (0, 7, "─"),
            (1, 1, "│"),
            (1, 5, "│"),
            (2, 1, "└"),
            (2, 2, "─"),
            (2, 3, "─"),
            (2, 4, "─"),
            (2, 5, "┘"),
        ),
    )


def _parallel_case():
    boxes = [_Box(0, 0, "fork"), _Box(0, 4, "toggle")]
    boxes.extend(_Box(0, 8 + 4 * index, "write") for index in range(8))
    boxes.append(_Box(0, 40, "end"))
    boxes.extend(_Box(2, 3 + 4 * index, "read") for index in range(9))
    boxes.append(_Box(2, 39, "end"))
    rails = [(0, 3, "─"), (1, 1, "│"), (2, 1, "└"), (2, 2, "─")]
    rails.extend((0, 7 + 4 * index, "─") for index in range(9))
    rails.extend((2, 6 + 4 * index, "─") for index in range(9))
    return _layout(boxes, rails, "11")


def _extra_cases():
    cases = [
        (_straight(("read", "push_top", "write"), "A"), 64),
        (_fork_case(), 64),
        (_reentry_case(), 8),
        (_parallel_case(), 64),
    ]
    cases.extend(
        (_straight(kinds), 64)
        for kinds in (
            ("one", "push_top", "empty", "pop_top", "write"),
            ("empty", "push_top", "pop_top", "write"),
            ("one", "push_bottom", "zero", "push_top", "pop_bottom", "write"),
            ("right", "one", "push_top", "left", "pop_top", "write"),
            ("left", "one", "push_bottom", "right", "left", "pop_bottom", "write"),
            ("toggle", "toggle", "write"),
        )
    )
    cases.extend((_switch_case(setter), 64) for setter in ("one", "zero", "empty"))
    cases.append((_memory_case(), 8))
    cases.append((_shared_case(), 64))
    return cases


def _switch_case(setter):
    return _layout(
        (
            _Box(2, 0, "fork"),
            _Box(2, 4, setter),
            _Box(2, 8, "switch"),
            _Box(0, 8, "one"),
            _Box(0, 12, "write"),
            _Box(0, 16, "end"),
            _Box(4, 8, "zero"),
            _Box(4, 12, "write"),
            _Box(4, 16, "end"),
        ),
        (
            (2, 3, "─"),
            (2, 7, "─"),
            (1, 9, "│"),
            (3, 9, "│"),
            (0, 11, "─"),
            (0, 15, "─"),
            (4, 11, "─"),
            (4, 15, "─"),
        ),
    )


def _memory_case():
    # First leave the one-node eastward; return from the north. Its remembered
    # east exit wins over the otherwise preferred clockwise (west) exit.
    boxes = (_Box(4, 0, "fork"), _Box(4, 4, "one"), _Box(4, 8, "write"))
    rails = [
        (4, 3, "─"),
        (4, 7, "─"),
        (4, 11, "─"),
        (4, 12, "┘"),
        (3, 12, "│"),
        (2, 12, "┐"),
        (2, 5, "┌"),
        (3, 5, "│"),
    ]
    rails.extend((2, column, "─") for column in range(6, 12))
    return _layout(boxes, rails)


def _shared_case():
    return _layout(
        (
            _Box(0, 0, "fork"),
            _Box(0, 4, "one"),
            _Box(0, 8, "one"),
            _Box(0, 12, "fork"),
            _Box(0, 16, "push_top"),
            _Box(0, 22, "write"),
            _Box(0, 26, "end"),
            _Box(2, 11, "pop_top"),
            _Box(4, 12, "write"),
            _Box(6, 11, "end"),
        ),
        (
            (0, 3, "─"),
            (0, 7, "─"),
            (0, 11, "─"),
            (0, 15, "─"),
            (0, 21, "─"),
            (0, 25, "─"),
            (1, 13, "│"),
            (3, 13, "│"),
            (5, 13, "│"),
        ),
    )
