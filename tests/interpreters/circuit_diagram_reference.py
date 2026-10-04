"""Independent scalar wiring graph and event/latch semantics."""

import re
from dataclasses import dataclass

LABEL = re.compile(r"(?<=[-./\\|])[0-9A-Za-z]+(?:\+[0-9A-Za-z]+)*(?=[-./\\|])")


DIRECTIONS = {
    "-": {(-1, 0), (1, 0)},
    "|": {(0, -1), (0, 1)},
    "/": {(-1, -1), (1, 1)},
    "\\": {(-1, 1), (1, -1)},
    ".": {(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0)},
}


@dataclass(frozen=True)
class Gate:
    kind: str
    point: tuple[int, int]
    inputs: tuple[frozenset, ...]
    outputs: tuple[frozenset, ...]


class WiringGraph:
    def __init__(self, lines, calls=None, extra_links=()):
        self.calls = calls or {}
        self.cells = {
            (x, -y): char
            for y, row in enumerate(lines)
            for x, char in enumerate(row)
            if char != " "
        }
        for point, (name, length, _arity) in self.calls.items():
            for x in range(point[0], point[0] + length):
                self.cells.pop((x, point[1]), None)
            self.cells[point] = name
        if any(
            point not in self.calls
            and char not in "-|/\\.=aAoOxX~:()< >%t".replace(" ", "")
            for point, char in self.cells.items()
        ):
            raise ValueError("scalar draft excludes labels, functions and clock")
        self.wires = {point for point, char in self.cells.items() if char in DIRECTIONS}
        links = {point: set() for point in self.wires}
        for point in self.wires:
            for vector in DIRECTIONS[self.cells[point]]:
                target = self.follow(point, vector)
                if (
                    target in self.wires
                    and (-vector[0], -vector[1]) in DIRECTIONS[self.cells[target]]
                ):
                    links[point].add(target)
                    links[target].add(point)
        for left, right in extra_links:
            if left not in self.wires or right not in self.wires:
                raise ValueError("label has no wire endpoints")
            links[left].add(right)
            links[right].add(left)
        components = []
        remaining = set(self.wires)
        while remaining:
            first = remaining.pop()
            group = {first}
            frontier = [first]
            while frontier:
                point = frontier.pop()
                for neighbor in links[point] - group:
                    group.add(neighbor)
                    remaining.discard(neighbor)
                    frontier.append(neighbor)
            components.append(frozenset(group))
        self.components = tuple(
            sorted(components, key=lambda group: min((-y, x) for x, y in group))
        )
        self.owner = {point: group for group in self.components for point in group}
        self.gates = []
        for point, kind in sorted(
            self.cells.items(), key=lambda item: (-item[0][1], item[0][0])
        ):
            if kind in DIRECTIONS or kind == "=":
                continue
            inputs = (
                () if kind in {"(", ")", "t"} else self.ports(point, -1, (1, 0, -1))
            )
            if kind == "~" and len(inputs) > 1:
                level = self.ports(point, -1, (0,))
                if level:
                    inputs = level
            output_point = (
                (point[0] + self.calls[point][1] - 1, point[1])
                if point in self.calls
                else point
            )
            outputs = (
                ()
                if kind == ":"
                else self.ports(
                    output_point,
                    1,
                    (0,)
                    if kind in {"(", ")", "t"}
                    else (1, -1)
                    if kind == "<"
                    else (1, 0, -1),
                )
            )
            if set(inputs) & set(outputs):
                raise ValueError("wiring feeds and is fed by the same gate")
            arity = (
                self.calls[point][2]
                if point in self.calls
                else 0
                if kind in {"(", ")", "t"}
                else 1
                if kind in {"~", ":", "<"}
                else 2
            )
            if len(inputs) != arity or len(outputs) != (
                0 if kind == ":" else 2 if kind == "<" else 1
            ):
                raise ValueError("wrong gate ports")
            if kind == ":" and self.cells.get((point[0] - 1, point[1])) != "-":
                raise ValueError("output requires a dash")
            self.gates.append(Gate(kind, point, inputs, outputs))

    def follow(self, point, vector):
        x, y = point
        dx, dy = vector
        target = x + dx, y + dy
        while self.cells.get(target) == "=":
            target = target[0] + dx, target[1] + dy
        return target

    def ports(self, point, side, rows):
        seen = set()
        ports = []
        for dy in rows:
            target = self.follow(point, (side, dy))
            if target in seen or target not in self.wires:
                continue
            if (-side, -dy) not in DIRECTIONS[self.cells[target]]:
                continue
            seen.add(target)
            ports.append(self.owner[target])
        return tuple(ports)


def decimal(text):
    value = 0
    for start in range(0, len(text), 9):
        chunk = text[start : start + 9]
        value = value * 10 ** len(chunk) + int(chunk)
    return value


class ClockTape:
    def __init__(self, seconds=0, provider=None):
        self.seconds = seconds
        self.position = 0
        self.provider = provider

    def read(self):
        self.position += 1
        return (self.provider() if self.provider is not None else self.seconds) % (
            1 << 32
        )


class BundleReference(WiringGraph):
    def __init__(
        self, lines, stdin="", calls=None, clock_seconds=0, symbols=None, clock=None
    ):
        self.clock_seconds = clock_seconds
        self.clock = clock if clock is not None else ClockTape(clock_seconds)
        labels = []
        skeleton = []
        symbols = symbols or {}
        calls = calls or {}
        for y, row in enumerate(lines):
            chars = list(row)
            for match in re.finditer(r"[0-9A-Za-z]+(?:\+[0-9A-Za-z]+)*", row):
                start, end = match.span()
                if (start, -y) in calls or match.group() in set("aAoOxXt"):
                    continue
                if (
                    start == 0
                    or end == len(row)
                    or row[start - 1] not in "-|/\\."
                    or row[end] not in "-|/\\."
                ):
                    raise ValueError(
                        "draft labels require wire endpoints on the same row"
                    )
                width = sum(
                    decimal(term)
                    if term.isascii() and term.isdecimal()
                    else symbols.get(term, 1)
                    for term in match.group().split("+")
                )
                if width < 1:
                    raise ValueError("empty labelled bundle")
                labels.append(((start - 1, -y), (end, -y), width))
                chars[start:end] = " " * (end - start)
            skeleton.append("".join(chars))
        super().__init__(
            skeleton, calls, ((left, right) for left, right, width in labels)
        )
        self.widths = dict.fromkeys(self.components)
        self.explicit = set()
        for left, right, width in labels:
            group = self.owner[left]
            assert self.owner[right] == group
            if group in self.explicit and self.widths[group] != width:
                raise ValueError("conflicting labels")
            self.widths[group] = width
            self.explicit.add(group)
        for gate in self.gates:
            if gate.kind in {"a", "A", "o", "O", "x", "X"}:
                output = gate.outputs[0]
                if output in self.explicit and self.widths[output] != 1:
                    raise ValueError("logic output width")
                self.widths[output] = 1
            elif gate.kind == "t":
                output = gate.outputs[0]
                if output in self.explicit and self.widths[output] != 32:
                    raise ValueError("clock requires 32-bit output")
                self.widths[output] = 32
        roots = set()
        for y, row in enumerate(lines):
            stripped = row.lstrip()
            if stripped.startswith("-"):
                roots.add(self.owner[len(row) - len(stripped), -y])
        for gate in self.gates:
            if gate.kind in {"(", ")", "t"}:
                roots.add(gate.outputs[0])
        for group in roots:
            if self.widths[group] is None:
                self.widths[group] = 1
        changed = True
        while changed:
            changed = False
            for gate in self.gates:
                if gate.point in self.calls:
                    inputs = tuple(self.widths[group] for group in gate.inputs)
                    if None in inputs:
                        continue
                    result = self.function_result(
                        gate, tuple((0,) * width for width in inputs), type_only=True
                    )
                    group = gate.outputs[0]
                    width = len(result)
                    if self.widths[group] is not None and self.widths[group] != width:
                        raise ValueError("function output width mismatch")
                    if self.widths[group] is None:
                        self.widths[group] = width
                        changed = True
                    continue
                if gate.kind in {"<", ">", "%"}:
                    inputs = tuple(self.widths[group] for group in gate.inputs)
                    if None in inputs:
                        continue
                    if gate.kind == "<":
                        if inputs[0] < 2:
                            raise ValueError("split creates an empty output bundle")
                        targets = tuple(
                            zip(
                                gate.outputs,
                                (inputs[0] // 2, inputs[0] - inputs[0] // 2),
                                strict=True,
                            )
                        )
                    else:
                        width = (
                            sum(inputs) if gate.kind == ">" else inputs[1] - inputs[0]
                        )
                        if width < 1:
                            raise ValueError("remove creates an empty output bundle")
                        targets = ((gate.outputs[0], width),)
                    for group, width in targets:
                        if (
                            self.widths[group] is not None
                            and self.widths[group] != width
                        ):
                            raise ValueError("mover width mismatch")
                        if self.widths[group] is None:
                            self.widths[group] = width
                            changed = True
                    continue
                if gate.kind != "~":
                    continue
                left, right = gate.inputs[0], gate.outputs[0]
                a, b = self.widths[left], self.widths[right]
                if a is not None and b is not None and a != b:
                    raise ValueError("NOT changes width")
                if a is not None and b is None:
                    self.widths[right] = a
                    changed = True
                if b is not None and a is None:
                    self.widths[left] = b
                    changed = True
        self.widths = {group: width or 1 for group, width in self.widths.items()}
        self.stdin = stdin
        self.offset = 0
        self.past_end = 0
        self.stdout = ""
        self.halted = False
        self.values = dict.fromkeys(self.components)
        self.latches = {gate: (None,) * len(gate.inputs) for gate in self.gates}
        arrivals = {group: [] for group in self.components}
        for y, row in enumerate(lines):
            stripped = row.lstrip()
            if stripped.startswith("-"):
                group = self.owner[len(row) - len(stripped), -y]
                arrivals[group].append(
                    tuple(self.input() for _ in range(self.widths[group]))
                )
        seconds = (
            self.clock.read() if any(gate.kind == "t" for gate in self.gates) else 0
        )
        for gate in self.gates:
            if gate.kind in {"(", ")", "t"}:
                group = gate.outputs[0]
                arrivals[group].append(
                    tuple((seconds >> index) & 1 for index in range(31, -1, -1))
                    if gate.kind == "t"
                    else (int(gate.kind == ")"),) * self.widths[group]
                )
        self.values = {
            group: self.merge(signals) for group, signals in arrivals.items()
        }

    def input(self):
        while self.offset < len(self.stdin):
            char = self.stdin[self.offset]
            self.offset += 1
            if char.isspace():
                continue
            if char not in "01":
                raise ValueError("input is not a bit")
            return int(char)
        self.past_end += 1
        return 0

    @staticmethod
    def merge(signals):
        if not signals:
            return None
        assert len({len(signal) for signal in signals}) == 1
        return tuple(sum(column) % 2 for column in zip(*signals, strict=True))

    def step(self):
        if self.halted:
            return
        next_values = {group: [] for group in self.components}
        fired = False
        for gate in self.gates:
            if gate.kind == ":":
                value = self.values[gate.inputs[0]]
                if value is not None:
                    self.stdout += "".join(map(str, value))
                continue
            if gate.kind in {"(", ")", "t"}:
                continue
            arrivals = tuple(self.values[group] for group in gate.inputs)
            remembered = tuple(
                new if new is not None else old
                for old, new in zip(self.latches[gate], arrivals, strict=True)
            )
            self.latches[gate] = remembered
            if all(new is None for new in arrivals) or None in remembered:
                continue
            if gate.point in self.calls:
                results = (self.function_result(gate, remembered),)
            elif gate.kind == "<":
                split = len(remembered[0]) // 2
                results = (remembered[0][:split], remembered[0][split:])
            elif gate.kind == ">":
                results = (remembered[0] + remembered[1],)
            elif gate.kind == "%":
                results = (remembered[1][len(remembered[0]) :],)
            elif gate.kind == "~":
                results = (tuple(1 - bit for bit in remembered[0]),)
            else:
                bits = tuple(bit for bundle in remembered for bit in bundle)
                ones = sum(bits)
                results = (
                    (
                        int(
                            {
                                "a": ones == len(bits),
                                "A": ones != len(bits),
                                "o": ones > 0,
                                "O": ones == 0,
                                "x": ones == 1,
                                "X": ones != 1,
                            }[gate.kind]
                        ),
                    ),
                )
            for output, result in zip(gate.outputs, results, strict=True):
                assert len(result) == self.widths[output]
                next_values[output].append(result)
            fired = True
        quiet = not fired and all(value is None for value in self.values.values())
        self.values = {
            group: self.merge(signals) for group, signals in next_values.items()
        }
        self.halted = quiet


BUILTINS = set("aAoOxX~:()<>%t")


class NamedReference(BundleReference):
    def __init__(
        self,
        lines,
        stdin="",
        definitions=None,
        active=(),
        clock_seconds=0,
        symbols=None,
        clock=None,
    ):
        self.definitions = dict(definitions or {})
        main = []
        index = 0
        while index < len(lines):
            row = lines[index]
            if row.strip().startswith("{"):
                name = row.strip()[1:].strip()
                body = []
                index += 1
                while index < len(lines) and lines[index].strip() != "}":
                    body.append(lines[index])
                    index += 1
                if index == len(lines):
                    raise ValueError("unterminated function")
                if name in "<>%":
                    index += 1
                    continue
                if not name.isascii() or not name.isalpha() or name in BUILTINS:
                    raise ValueError("invalid function name")
                if name in self.definitions:
                    raise ValueError("duplicate function")
                self.definitions[name] = body
            else:
                main.append(row)
            index += 1
        if any(
            sum(row.lstrip().startswith("-") for row in body) not in (1, 2)
            for body in self.definitions.values()
        ):
            raise ValueError("function requires one or two input ports")
        self.main = main
        self.active = active
        calls = {}
        for y, row in enumerate(main):
            for word in re.finditer("[A-Za-z]+", row):
                name = word.group()
                if name not in self.definitions:
                    continue
                arity = sum(
                    line.lstrip().startswith("-") for line in self.definitions[name]
                )
                if arity not in (1, 2):
                    raise ValueError("function requires one or two input ports")
                calls[word.start(), -y] = name, len(name), arity
        super().__init__(main, stdin, calls, clock_seconds, symbols, clock)

    def function_result(self, gate, inputs, *, type_only=False):
        name = gate.kind
        if name in self.active:
            raise ValueError("recursive function dependency")
        body = self.definitions[name]
        rows = [row for row in body if row.lstrip().startswith("-")]
        if len(rows) != len(inputs):
            raise ValueError("function input count")
        bindings = {}
        for row, bundle in zip(rows, inputs, strict=True):
            labels = [
                text for text in LABEL.findall(row) if text not in self.definitions
            ]
            if not labels:
                if len(bundle) != 1:
                    raise ValueError("one-bit input width required")
            else:
                terms = labels[0].split("+")
                if all(term.isascii() and term.isdecimal() for term in terms):
                    if sum(map(decimal, terms)) != len(bundle):
                        raise ValueError("numeric input width mismatch")
                elif len(terms) == 1 and terms[0].isascii() and terms[0].isalpha():
                    symbol = terms[0]
                    if symbol in bindings and bindings[symbol] != len(bundle):
                        raise ValueError("symbol binding mismatch")
                    bindings[symbol] = len(bundle)
                else:
                    raise ValueError("input label requires a number or name")

        def expand(match):
            if match.group() in self.definitions:
                return match.group()
            return "+".join(
                str(bindings.get(term, term)) for term in match.group().split("+")
            )

        expanded = [LABEL.sub(expand, row) for row in body]
        clock = ClockTape(self.clock.seconds) if type_only else self.clock
        machine = NamedReference(
            expanded,
            "".join(str(bit) for bundle in inputs for bit in bundle),
            self.definitions,
            (*self.active, name),
            self.clock.seconds,
            clock=clock,
        )
        seen = set()
        for _ in range(100):
            if machine.halted:
                if not machine.stdout:
                    raise ValueError("function returns no bits")
                return tuple(map(int, machine.stdout))
            key = (
                tuple(value is not None for value in machine.values.values()),
                tuple(
                    tuple(slot is not None for slot in slots)
                    for slots in machine.latches.values()
                ),
            )
            if key in seen:
                raise ValueError("function has an exact event cycle")
            seen.add(key)
            machine.step()
        raise TimeoutError(
            "function observation bound reached; not proven to terminate"
        )
