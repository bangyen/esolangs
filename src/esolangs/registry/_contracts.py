"""Boolean I/O contracts, independent of example programs and documentation."""

from dataclasses import dataclass
from typing import Literal

type AnswerMode = Literal["output", "dump", "termination"]
#: The input shapes whose bits arrive as one unseparated character run.
CHAR_STREAMS: frozenset[str] = frozenset({"char_stream", "char_stream_cyclic"})

type InputShape = Literal[
    "line_per_bit",
    "char_stream",
    "char_stream_cyclic",
    "row_index",
    "row_number",
]
type WidthEffect = Literal["layout", "wrap", "none"]
type SourceForm = Literal["text", "raster"]
type StateModel = Literal[
    "register", "tape", "stack", "grid", "queue", "program", "variables", "other"
]
type GeneratorShape = Literal["tree", "reducing", "lookup"]


@dataclass(frozen=True, slots=True)
class BooleanContract:
    """Input encoding and answer extraction for a generated Boolean program."""

    alphabet: tuple[str, str] = ("0", "1")
    input_shape: InputShape = "line_per_bit"
    answer_mode: AnswerMode = "output"
    answer_pattern: str = ""
    answer_values: tuple[str, str] = ("0", "1")
    note: str = ""
    ignores_whitespace: bool = False
    #: A newline ends the set a program reads; generated programs read one.
    input_sets: bool = False
