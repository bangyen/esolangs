"""Validate truth-table syntax incrementally on a native stdin pipe."""

from __future__ import annotations

from encodings.utf_8 import IncrementalDecoder
from typing import TYPE_CHECKING

from esolangs.exceptions import ArgumentError
from esolangs.runtime._input import input_read_error

if TYPE_CHECKING:
    from esolangs.registry import LanguageDeclaration


class _TruthTablePipeCheck:
    """Reject invalid input while a producer may still hold the pipe open."""

    def __init__(
        self,
        declaration: LanguageDeclaration | None,
        *,
        expected_inputs: int | None = None,
    ) -> None:
        self.declaration = declaration
        self.backend = None if declaration is None else declaration.backend
        self.expected_inputs = expected_inputs
        self.decoder = IncrementalDecoder()
        self.at_start = True
        self.rows = 0
        self.trailing_space = False

    def __call__(self, chunk: bytes, received: bytearray) -> None:
        pending, _ = self.decoder.getstate()
        try:
            text = self.decoder.decode(chunk)
        except UnicodeDecodeError as error:
            offset = len(received) - len(chunk) - len(pending)
            raise input_read_error(error, byte_offset=offset) from error
        if self.at_start and text:
            text = text.removeprefix("\ufeff")
            self.at_start = False

        content = text if self.rows else text.lstrip()
        body = content.rstrip()
        bits = body.count("0") + body.count("1")
        if bits != len(body) or (body and self.trailing_space):
            from esolangs.generation.helpers import _validate_truth_table

            # Only the error path needs the full prefix for the existing diagnostic.
            prefix = IncrementalDecoder().decode(received)
            _validate_truth_table(prefix.removeprefix("\ufeff").strip())
        self.rows += bits
        self.trailing_space |= len(body) != len(content)
        if not self.rows:
            return
        arity = (self.rows - 1).bit_length()
        backend = self.backend
        if backend is not None and backend.max_inputs is not None:
            assert self.declaration is not None
            backend.check_arity(self.declaration.name, arity)
        inputs = self.expected_inputs
        if inputs is not None and arity > inputs:
            raise ArgumentError(
                f"piped truth table exceeds the {1 << inputs} rows required "
                f"by --bits ({inputs} input bits)"
            )
