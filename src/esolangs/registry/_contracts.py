"""Boolean I/O contracts, independent of example programs and documentation."""

from dataclasses import dataclass
from typing import Literal

type AnswerMode = Literal["output", "dump", "termination"]
type InputShape = Literal[
    "line_per_bit",
    "char_stream",
    "char_stream_padded",
    "char_stream_cyclic",
    "row_index",
]
type WidthEffect = Literal["layout", "wrap", "none"]


@dataclass(frozen=True, slots=True)
class BooleanContract:
    """Input encoding and answer extraction for a generated Boolean program."""

    parameterized: bool = False
    alphabet: tuple[str, str] = ("0", "1")
    input_shape: InputShape = "line_per_bit"
    ghost_digit: bool = False
    answer_mode: AnswerMode = "output"
    answer_pattern: str = ""
    answer_values: tuple[str, str] = ("0", "1")
    note: str = ""
    ignores_whitespace: bool = False
    #: A newline ends the set a program reads; generated programs read one.
    input_sets: bool = False
