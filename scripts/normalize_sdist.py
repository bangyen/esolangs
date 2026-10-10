"""Normalize sdist archive timestamps to SOURCE_DATE_EPOCH."""

from __future__ import annotations

import gzip
import io
import os
import tarfile
from pathlib import Path


def normalize(path: Path, epoch: int) -> None:
    """Preserve payloads while fixing gzip and tar metadata deterministically."""
    buffer = io.BytesIO()
    with (
        tarfile.open(path, "r:gz") as source,
        tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as target,
    ):
        for member in source.getmembers():
            member.mtime = epoch
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.pax_headers = {
                key: value
                for key, value in member.pax_headers.items()
                if key not in {"mtime", "atime", "ctime"}
            }
            target.addfile(
                member, source.extractfile(member) if member.isfile() else None
            )
    with (
        path.open("wb") as stream,
        gzip.GzipFile(
            filename="", mode="wb", fileobj=stream, mtime=epoch
        ) as compressed,
    ):
        compressed.write(buffer.getvalue())


if __name__ == "__main__":
    import sys

    for name in sys.argv[1:]:
        normalize(Path(name), int(os.environ["SOURCE_DATE_EPOCH"]))
