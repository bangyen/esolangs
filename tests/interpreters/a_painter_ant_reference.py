"""Independent white-set ant; north is +1j, unlike the native screen grid."""

from dataclasses import dataclass, field


@dataclass
class Reference:
    source: str
    white: set[complex] = field(default_factory=set)
    painted: set[complex] = field(default_factory=set)
    visited: set[complex] = field(default_factory=lambda: {0j})
    position: complex = 0j
    cursor: int = 0

    def __post_init__(self):
        self.source = "".join(self.source.split())
        if any(command not in "nNeEsSwWpP" for command in self.source):
            raise ValueError("invalid instruction")

    def step(self):
        if not self.source:
            return
        command = self.source[self.cursor]
        if command in "pP":
            self.painted.add(self.position)
            if command == "P":
                self.white.add(self.position)
            else:
                self.white.discard(self.position)
        else:
            target = (
                self.position + {"n": 1j, "e": 1, "s": -1j, "w": -1}[command.lower()]
            )
            if (target in self.white) == (command in "NESW"):
                self.position = target
                self.visited.add(target)
        self.cursor = (self.cursor + 1) % len(self.source)

    def state(self):
        return frozenset(self.white), self.position, self.cursor

    def storage_state(self):
        cells = frozenset((p, int(p in self.white)) for p in self.painted)
        return cells, self.position, self.cursor

    def native_view(self):
        cells = frozenset(
            ((int(p.real), -int(p.imag)), int(p in self.white)) for p in self.painted
        )
        return cells, int(self.position.real), -int(self.position.imag), self.cursor

    def render(self):
        xs = [int(p.real) for p in self.visited]
        ys = [int(p.imag) for p in self.visited]
        raster = {(int(p.real), int(p.imag)): "#" for p in self.white}
        raster[int(self.position.real), int(self.position.imag)] = (
            "@" if self.position in self.white else "o"
        )
        return "\n".join(
            "".join(raster.get((x, y), ".") for x in range(min(xs), max(xs) + 1))
            for y in range(max(ys), min(ys) - 1, -1)
        )
