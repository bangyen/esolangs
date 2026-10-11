"""Run one of the ``tests/proofs/*_certificate.py`` checkers on a JSON certificate."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]


def run_checker(tmp_path: Path, script: str, data: dict[str, Any]) -> str:
    """Write ``data`` to a file, check it with ``script``, and return stdout."""
    path = tmp_path / "certificate.json"
    path.write_text(json.dumps(data))
    module = f"tests.proofs.{script.removesuffix('.py')}"
    return subprocess.run(
        [sys.executable, "-m", module, str(path)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
