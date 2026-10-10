"""Spool bounded diagnostics and stop producers that exceed the byte budget."""

from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, cast

MAX_LOG_BYTES = 8 * 1024 * 1024
MARKER = b"\n[diagnostic byte limit exceeded]\n"


def spool(
    stream: BinaryIO,
    path: Path,
    limit: int,
    stop: Callable[[], None],
    tee: Callable[[bytes], None] | None = None,
) -> None:
    """Keep a bounded prefix and overflow excerpt, then stop the process tree."""
    written = 0
    with path.open("wb") as output:
        while chunk := cast(bytes, getattr(stream, "read1", stream.read)(8192)):
            if written + len(chunk) > limit - len(MARKER):
                available = max(0, limit - written - len(MARKER))
                excerpt = chunk[-available:] if available else b""
                output.write(excerpt)
                output.write(MARKER)
                output.flush()
                if tee is not None:
                    tee(MARKER)
                stop()
                return
            output.write(chunk)
            output.flush()
            written += len(chunk)
            if tee is not None:
                tee(chunk)
