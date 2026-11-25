"""Reject an invalid portable document pipe while it is still open."""

from __future__ import annotations

from codecs import BOM_UTF8
from collections.abc import Callable
from encodings.utf_8 import IncrementalDecoder as UTF8Decoder
from typing import NoReturn

from esolangs.cli.hints import _with_cli_hint
from esolangs.exceptions import ProgramError
from esolangs.portable import _portable_bom_error
from esolangs.raster.png import _SIGNATURE as _PNG_SIGNATURE
from esolangs.runtime._source import _GZIP_SIGNATURE


def _native_binary_format(data: bytes | bytearray) -> str | None:
    """Recognize native binary source by its signature."""
    for signature, kind in ((_PNG_SIGNATURE, "PNG"), (_GZIP_SIGNATURE, "gzip")):
        if data.startswith(signature):
            return kind
    return None


def _portable_pipe_check(
    option: str, hint: Callable[[], str]
) -> Callable[[bytes, bytearray], None]:
    """Check UTF-8 and the JSON object opener; the full document still needs EOF."""
    decoder = UTF8Decoder()
    started = False

    def refuse(expectation: str) -> NoReturn:
        raise _with_cli_hint(
            ProgramError(f"stdin: {option} expects {expectation}"), hint()
        )

    def check(chunk: bytes, received: bytearray) -> None:
        nonlocal started
        if kind := _native_binary_format(received):
            refuse(f"portable JSON; the input is native {kind}")
        if received.startswith(BOM_UTF8):
            raise _portable_bom_error("stdin")
        try:
            text = decoder.decode(chunk)
        except UnicodeDecodeError:
            # Re-decode only on failure to retain the complete stream's byte offset.
            received.decode("utf-8")
            raise
        if not started and (prefix := text.lstrip(" \t\r\n")):
            if not prefix.startswith("{"):
                refuse("a portable JSON object")
            started = True

    return check
