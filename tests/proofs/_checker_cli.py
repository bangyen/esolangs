"""Run one of the ``scripts/*_certificate.py`` checkers on a JSON certificate."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def run_checker(tmp_path: Path, script: str, data: dict[str, Any]) -> str:
    """Write ``data`` to a file, check it with ``script``, and return stdout."""
    path = tmp_path / "certificate.json"
    path.write_text(json.dumps(data))
    return subprocess.run(
        [sys.executable, str(_SCRIPTS / script), str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
