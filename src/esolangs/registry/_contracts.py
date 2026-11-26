"""Boolean I/O contracts, independent of example programs and documentation."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import ProgramError
from esolangs.runtime._input import InputFrame, RecordFrame, SymbolFrame
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.memory import format_integer

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

    def encode_row(self, name: str, bits: tuple[int, ...] | list[int]) -> str:
        """Encode one validated row for this contract."""
        return self.row_encoder(name)(bits)

    def row_encoder(self, name: str) -> Callable[[tuple[int, ...] | list[int]], str]:
        """Validate the framing once and bind it for subsequent checked rows."""
        shape = self.input_shape
        if shape in ("row_index", "row_number"):
            offset = int(shape == "row_number")

            def number(bits: tuple[int, ...] | list[int]) -> str:
                row = int("".join("01"[bit] for bit in bits), 2)
                return format_integer(row + offset) + "\n"

            return number
        if shape not in ("line_per_bit", "char_stream", "char_stream_cyclic"):
            raise ProgramError(f"{name} has an invalid input shape")
        zero, one = symbol_pair(name, self.alphabet, "input encoding")
        stream = shape in CHAR_STREAMS
        if stream:
            if self.input_sets and ("\n" in zero or "\n" in one):
                raise ProgramError(
                    f"{name} has an invalid input encoding. "
                    "A newline ends the input set."
                )
            left, right = zero, one
            if self.ignores_whitespace:
                left, right = "".join(zero.split()), "".join(one.split())
            # Two words form a uniquely decodable code exactly when they do not commute.
            if left + right == right + left:
                raise ProgramError(
                    f"{name} has an invalid input encoding. "
                    "The two bit values are ambiguous when concatenated."
                )
        elif "\n" in zero or "\n" in one:
            raise ProgramError(
                f"{name} has an invalid input encoding. Each bit must fit on one line."
            )
        elif zero.removesuffix("\r") == one.removesuffix("\r"):
            raise ProgramError(
                f"{name} has an invalid input encoding. "
                "The two bit lines match after CRLF decoding."
            )
        if not stream:
            zero += "\n"
            one += "\n"

        def encode(bits: tuple[int, ...] | list[int]) -> str:
            return "".join([one if bit else zero for bit in bits])

        return encode

    def input_frame(self, arity: int | None) -> RecordFrame | None:
        """Return the read boundary for one arity-tagged record."""
        if arity is None or not self.frame_stdin:
            return None
        if self.input_shape in ("row_index", "row_number"):
            return InputFrame(1, lines=True)
        if self.input_shape == "line_per_bit":
            return InputFrame(arity, lines=True)
        zero, one = self.alphabet
        if len(zero) == len(one):
            return InputFrame(arity * len(zero), lines=False)
        if zero.startswith(one) or one.startswith(zero):
            raise ProgramError(
                "framing variable-width bit symbols requires a prefix-free alphabet"
            )
        return SymbolFrame(arity, (zero, one))


def symbol_pair(name: str, values: object, encoding: str) -> tuple[str, str]:
    """Validate a scoped contract's two distinct spellings for the bits."""
    if _has_backing_type(values, tuple) and tuple.__len__(values) == 2:
        zero, one = tuple.__iter__(values)
        if _has_backing_type(zero, str) and _has_backing_type(one, str):
            zero, one = str.__str__(zero), str.__str__(one)
            if zero != one:
                return zero, one
    raise ProgramError(
        f"{name} has an invalid {encoding}; expected two distinct strings"
    )


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
