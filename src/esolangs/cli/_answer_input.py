"""Read answer streams and reject malformed UTF-8 before EOF."""

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
    from collections.abc import Callable
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
        """Return a bounded suffix and retain the last non-whitespace character."""
        _read_answer_input(stdin, deadline, self._add)
        return self.text


def _snapshot_answer(stdin: TextIO, deadline: float | None) -> str:
    """Retain all output for answer patterns that can span multiple chunks."""
    parts: list[str] = []
    _read_answer_input(stdin, deadline, parts.append)
    return "".join(parts)


def _read_answer_input(
    stdin: TextIO, deadline: float | None, consume: Callable[[str], None]
) -> None:
    """Stream fresh native input and preserve managed reader behavior."""
    if _has_backing_type(stdin, TextIOWrapper) and not _custom_text_reader(stdin):
        stream = stdin.buffer
        if isinstance(stream, BufferedReader) and type(stream.raw) is FileIO:
            try:
                TextIOWrapper.reconfigure(stdin, errors=stdin.errors)
            except UnsupportedOperation:
                pass  # Preserve prefetched characters and decoder state.
            else:
                _read_native(stream, deadline, consume)
                return
    consume(_snapshot_stdin(stdin, deadline))


def _read_native(
    stream: BufferedReader, deadline: float | None, consume: Callable[[str], None]
) -> None:
    decoder = UTF8Decoder()
    offset = 0

    def decode(data: bytes, *, final: bool = False) -> None:
        nonlocal offset
        pending, _ = decoder.getstate()
        try:
            consume(decoder.decode(data, final=final))
        except UnicodeDecodeError as error:
            raise input_read_error(error, byte_offset=offset - len(pending)) from error
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
                return
