"""Character and integer-token spellings of raw input values."""

from dataclasses import dataclass

from esolangs.interpreters.io import IO

INPUT_FRAMINGS = ("characters", "integer_tokens")


@dataclass(frozen=True)
class InputFraming:
    input_framing: str = "characters"

    def __post_init__(self) -> None:
        if self.input_framing not in INPUT_FRAMINGS:
            raise ValueError("input_framing must be characters or integer_tokens")

    def read(self, io: IO) -> int:
        return (
            io.input_num()
            if self.input_framing == "integer_tokens"
            else io.input_char()
        )
