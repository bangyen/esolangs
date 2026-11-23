"""Boolean I/O contracts, independent of example programs and documentation."""

import re
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import ProgramError
from esolangs.runtime._validate import _has_backing_type

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
    answer_pattern: str | re.Pattern[str] = ""
    answer_values: tuple[str, str] = ("0", "1")
    note: str = ""
    ignores_whitespace: bool = False
    #: A newline ends the set a program reads; generated programs read one.
    input_sets: bool = False
    #: Give arity-tagged programs a single record at the input port.
    frame_stdin: bool = False


def answer_pattern_text(name: str, pattern: object) -> str | None:
    """Return a portable text pattern with its matching flags."""
    if _has_backing_type(pattern, str):
        return str.__str__(pattern) or None
    if not _has_backing_type(pattern, re.Pattern) or not _has_backing_type(
        pattern.pattern, str
    ):
        raise ProgramError(f"{name} has an invalid answer pattern; expected text")
    flags = "".join(
        letter
        for flag, letter in (
            (re.ASCII, "a"),
            (re.IGNORECASE, "i"),
            (re.MULTILINE, "m"),
            (re.DOTALL, "s"),
            (re.VERBOSE, "x"),
        )
        if pattern.flags & flag
    )
    prefix = f"(?{flags})" if flags else ""
    # A compiled empty pattern matches empty strings. Empty declaration text
    # instead selects the last-character decoder.
    return prefix + str.__str__(pattern.pattern) or "(?:)"
