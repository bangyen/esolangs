"""Read and validate PNG chunk framing for pixels and source tags."""

import struct
import zlib
from collections.abc import Buffer, Iterator

from esolangs.exceptions import ArgumentError, EsolangError
from esolangs.runtime._files import _STREAM_DEADLINE, _time_remaining
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.source_hints import display_label, syntax_error

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_REEXPORT = "restore or re-export the complete PNG image"


def _backing_bytes(data: Buffer) -> bytes:
    """Snapshot an image buffer, bypassing overrides on bytes and bytearrays."""
    if type(data) is bytes:
        return data
    if _has_backing_type(data, bytes):
        return bytes.__bytes__(data)
    deadline = _STREAM_DEADLINE.get()
    _time_remaining(deadline)
    if _has_backing_type(data, bytearray):
        return bytes(bytearray.copy(data))
    try:
        with memoryview(data) as view:
            _time_remaining(deadline)
            return view.tobytes()
    except EsolangError:
        raise
    except TypeError as error:
        raise ArgumentError(
            f"PNG data must be bytes, got {type(data).__name__}"
        ) from error
    except (BufferError, ValueError) as error:
        raise ArgumentError(f"cannot read PNG data: {error}") from error


def _chunk_label(kind: bytes) -> str:
    """Render an untrusted chunk type for diagnostics."""
    return display_label(kind.decode("ascii", "replace"))


def _chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Yield validated chunks through the end of the PNG datastream."""
    deadline = _STREAM_DEADLINE.get()
    _time_remaining(deadline)
    if data[:8] != _SIGNATURE:
        raise syntax_error(
            "not a PNG file (bad signature)",
            "export the image as PNG instead of renaming another image format",
        )
    pos = 8
    while pos + 8 <= len(data):
        _time_remaining(deadline)
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if len(body) != length:
            raise syntax_error(
                f"truncated {_chunk_label(kind)} chunk",
                ("restore or re-export the complete PNG file; this chunk is truncated"),
            )
        crc = data[pos + 8 + length : pos + 12 + length]
        if len(crc) != 4:
            raise syntax_error(
                f"truncated {_chunk_label(kind)} chunk CRC",
                ("restore or re-export the complete PNG file including its checksums"),
            )
        if struct.unpack(">I", crc)[0] != zlib.crc32(kind + body) & 0xFFFFFFFF:
            raise syntax_error(
                f"invalid {_chunk_label(kind)} chunk CRC",
                (
                    "restore or re-export the PNG; its chunk checksum does not "
                    "match the data"
                ),
            )
        _time_remaining(deadline)
        if kind == b"IEND":
            if body:
                raise syntax_error("PNG IEND chunk must be empty", _REEXPORT)
            yield kind, body
            return
        yield kind, body
        pos += 12 + length  # length + type + body + CRC
    missing = "IHDR" if pos == len(_SIGNATURE) else "complete IEND"
    raise syntax_error(f"PNG has no {missing} chunk", _REEXPORT)
