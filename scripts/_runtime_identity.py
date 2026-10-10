"""Identify the Python runtime and installed dependency versions for evidence."""

import hashlib
import importlib.metadata
import platform
import sys
from pathlib import Path
from typing import Any


def fingerprint() -> dict[str, Any]:
    """Record interpreter, platform, dependency versions and the dependency lock."""
    lock = Path(__file__).resolve().parents[1] / "uv.lock"
    return {
        "python": sys.version,
        "implementation": sys.implementation.name,
        "cache_tag": sys.implementation.cache_tag,
        "executable": str(Path(sys.executable).resolve()),
        "prefix": sys.prefix,
        "platform": sys.platform,
        "machine": platform.machine(),
        "dependencies": sorted(
            (distribution.metadata["Name"], distribution.version)
            for distribution in importlib.metadata.distributions()
        ),
        "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
    }
