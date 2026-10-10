"""Fingerprint the executable and file arguments of a reference command."""

import hashlib
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _reference_process import run


def fingerprint(template: str) -> dict[str, Any]:
    """Record exact arguments, executable version and hashes of existing files."""
    arguments = shlex.split(template)
    if not arguments:
        raise ValueError("empty reference command")
    executable = shutil.which(arguments[0])
    if executable is None:
        raise ValueError("reference executable cannot be resolved")
    files = {}
    inline = False
    for name in [executable, *arguments[1:]]:
        if inline:
            inline = False
            continue
        if name in {"-c", "-m"}:
            inline = True
            continue
        if "{program}" in name:
            continue
        path = Path(name)
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(65536):
                    digest.update(chunk)
            files[str(path.resolve())] = digest.hexdigest()
    code, output, error, status = run([executable, "--version"], b"", 1, 16384)
    return {
        "template": template,
        "arguments": arguments,
        "executable": str(Path(executable).resolve()),
        "files": files,
        "version": {
            "exit": code,
            "stdout": output.decode("utf-8", "replace"),
            "stderr": error.decode("utf-8", "replace"),
            "status": status,
        },
    }
