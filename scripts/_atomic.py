"""Replace complete text files without exposing partial writes."""

import os
import tempfile
from pathlib import Path


def write_text(path: Path, text: str) -> None:
    """Flush a sibling temporary file and replace the destination atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # newline="" keeps the bytes exactly as written: on Windows the
        # default text mode translates "\n" to "\r\n", which would make a
        # content hash (durations_sha256) disagree with the file it names.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
