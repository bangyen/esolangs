"""Read last-character answers from stdin with a bounded diagnostic tail."""

from __future__ import annotations

from encodings.utf_8 import IncrementalDecoder as UTF8Decoder
from io import BufferedReader, FileIO, TextIOWrapper, UnsupportedOperation
from typing import TYPE_CHECKING

from esolangs.cli.io import _custom_text_reader, _read_stdin_bytes, _snapshot_stdin
from esolangs.operations.boolean_io import _ANSWER_TAIL_SIZE
from esolangs.runtime._files import _BLOCK, stream_read_deadline
from esolangs.runtime._input import input_read_error
from esolangs.runtime._validate import _has_backing_type

if TYPE_CHECKING:
    from typing import TextIO


class _AnswerTail:
    """Retain the last non-whitespace character and a diagnostic suffix."""

    def __init__(self) -> None:
        self.text = ""
        self.last_character: str | None = None

    def _add(self, text: str) -> None:
        if last := text.rstrip()[-1:]:
            self.last_character = last
        self.text = (self.text + text[-_ANSWER_TAIL_SIZE:])[-_ANSWER_TAIL_SIZE:]

    def snapshot(self, stdin: TextIO, deadline: float | None) -> str:
        """Summarize fresh native input and preserve managed reader behavior."""
        if _has_backing_type(stdin, TextIOWrapper) and not _custom_text_reader(stdin):
            stream = stdin.buffer
            if isinstance(stream, BufferedReader) and type(stream.raw) is FileIO:
                try:
                    TextIOWrapper.reconfigure(stdin, errors=stdin.errors)
                except UnsupportedOperation:
                    pass  # Preserve prefetched characters and decoder state.
                else:
                    return self._read_native(stream, deadline)
        self._add(_snapshot_stdin(stdin, deadline))
        return self.text

    def _read_native(self, stream: BufferedReader, deadline: float | None) -> str:
        decoder = UTF8Decoder()
        offset = 0

        def decode(data: bytes, *, final: bool = False) -> None:
            nonlocal offset
            pending, _ = decoder.getstate()
            try:
                self._add(decoder.decode(data, final=final))
            except UnicodeDecodeError as error:
                raise input_read_error(
                    error, byte_offset=offset - len(pending)
                ) from error
            offset += len(data)

        def check_chunk(chunk: bytes, _buffer: bytearray) -> None:
            decode(chunk)

        with stream_read_deadline(deadline):
            while True:
                start = offset
                data = _read_stdin_bytes(
                    stream, deadline, size=_BLOCK, pipe_check=check_chunk
                )
                final = len(data) < _BLOCK
                # Pipe chunks were decoded as they arrived.
                if final or offset == start:
                    decode(data[offset - start :], final=final)
                if final:
                    return self.text
