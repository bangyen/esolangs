"""LaserFuck exhausted-input choices."""

from dataclasses import dataclass

from esolangs._brainfuck import EOF_POLICIES


@dataclass(frozen=True)
class LaserfuckDialect:
    eof: str = "error"

    def __post_init__(self) -> None:
        if self.eof not in EOF_POLICIES:
            raise ValueError("eof must be error, zero, minus_one or unchanged")

    def exhausted(self, previous: int) -> int:
        if self.eof == "error":
            raise EOFError("LaserFuck input exhausted")
        return (
            previous
            if self.eof == "unchanged"
            else -1
            if self.eof == "minus_one"
            else 0
        )
