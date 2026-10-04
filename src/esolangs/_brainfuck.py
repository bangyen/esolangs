"""Shared Brainfuck arithmetic, tape boundaries and exhausted-input choices."""

from dataclasses import dataclass

from esolangs._dialects import LineDialect
from esolangs.exceptions import HaltError


@dataclass(frozen=True)
class BrainfuckDialect:
    cell_modulus: int | None = 256
    tape_size: int | None = None
    boundary: str = "clamp"
    eof: str = "error"

    def __post_init__(self) -> None:
        LineDialect(
            self.cell_modulus,
            self.tape_size,
            self.boundary if self.tape_size is not None else "error",
        )
        if self.boundary not in ("clamp", "error", "wrap"):
            raise ValueError("boundary must be clamp, error or wrap")
        if self.boundary == "wrap" and self.tape_size is None:
            raise ValueError("wrap requires tape_size")
        if self.eof not in ("error", "zero", "minus_one", "unchanged"):
            raise ValueError("eof must be error, zero, minus_one or unchanged")

    def cell(self, value: int) -> int:
        return value if self.cell_modulus is None else value % self.cell_modulus

    def pointer(self, value: int) -> int:
        if self.tape_size is not None:
            return LineDialect(
                tape_size=self.tape_size, boundary=self.boundary
            ).pointer(value)
        if value >= 0:
            return value
        if self.boundary == "clamp":
            return 0
        raise HaltError("Brainfuck pointer left the tape")

    def exhausted(self, previous: int) -> int:
        if self.eof == "error":
            raise EOFError("Brainfuck input exhausted")
        return (
            previous
            if self.eof == "unchanged"
            else self.cell(-1 if self.eof == "minus_one" else 0)
        )

    def require_cells(self, count: int) -> None:
        """Reject settings unable to hold this ASCII-output construction."""
        if self.cell_modulus is not None and self.cell_modulus < 50:
            raise ValueError("Boolean generation requires cell_modulus at least 50")
        if self.tape_size is not None and self.tape_size < count:
            raise ValueError(f"Boolean generation requires at least {count} tape cells")


DEFAULT_DIALECT = BrainfuckDialect()
