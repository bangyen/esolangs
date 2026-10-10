"""Run screen setup and publication in killable, output-bounded processes."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "screens"))
from _atomic import write_text
from _reference_process import run as run_process
from _screen_evidence import LIMIT


def run(
    operation: str,
    payload: dict[str, Any],
    timeout: float,
    *,
    script: Path | None = None,
) -> dict[str, Any]:
    """Return bounded phase evidence; abort on timeout, overflow or worker failure."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise TimeoutError(f"{operation}: phase deadline exceeded")
    raw = json.dumps(payload).encode()
    if len(raw) > LIMIT:
        raise ValueError("phase input exceeds 32 MiB")
    code, output, error, status = run_process(
        [sys.executable, str(script or Path(__file__)), operation], raw, timeout, LIMIT
    )
    if status == "timeout":
        raise TimeoutError(f"{operation}: phase deadline exceeded")
    if status is not None or code != 0:
        raise ValueError(
            f"{operation}: phase failed ({status or code}): "
            f"{error[-4096:].decode('utf-8', 'replace')}"
        )
    result = json.loads(output)
    if not isinstance(result, dict):
        raise ValueError("phase result must be an object")
    return result


def execute(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Perform one setup or publication operation inside the bounded worker."""
    if operation == "allocate":
        directory = Path(payload["root"]) / "notes/screens"
        directory.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(
            prefix=payload["screen"] + "-", suffix=".json", dir=directory
        )
        os.close(fd)
        report = payload.get("report") or name
        if report != name:
            Path(name).unlink()
        return {"name": name, "report": report}
    if operation == "metadata":
        from _runtime_identity import fingerprint as runtime_fingerprint
        from benchmark import source_identity

        return {"checkout": source_identity(), "runtime": runtime_fingerprint()}
    if operation == "reference":
        from _reference_identity import fingerprint

        return fingerprint(payload["template"])
    if operation == "sharing":
        from _build import TABLES, size_cases
        from sharing import PARITY, sample

        count, languages = payload["count"], payload["languages"]
        planned = len(languages) * (count + 258)
        # JSON stores each hex ID in 68 bytes and each 32-bit table in 36.
        if planned * 68 + count * 36 + 1024 > LIMIT:
            raise ValueError("sharing corpus exceeds 32 MiB")
        tables = sample(count, payload["seed"])
        return {
            "tables": tables,
            "case_ids": [
                identifier
                for name in languages
                for corpus, scope in (
                    (list(PARITY.values()), "parity"),
                    (TABLES, "three"),
                    (tables, "five"),
                )
                for identifier in size_cases(name, corpus, scope)
            ],
        }
    if operation == "constant":
        from _build import TABLES, size_cases
        from constant import PARITY, sample

        count, languages = payload["count"], payload["languages"]
        planned = len(languages) * (count + 258)
        if planned * 68 + count * 36 + 1024 > LIMIT:
            raise ValueError("constant corpus exceeds 32 MiB")
        tables = sample(count, payload["seed"])
        return {
            "tables": tables,
            "case_ids": [
                identifier
                for name in languages
                for corpus, scope in (
                    (list(PARITY.values()), "parity"),
                    (TABLES, "three"),
                    (tables, "five"),
                )
                for identifier in size_cases(name, corpus, scope)
            ],
        }
    if operation == "resume":
        from _screen_evidence import resume

        return {
            "cases": resume(
                Path(payload["path"]),
                payload["identity"],
                payload["plan"],
                payload["screen"],
            )
        }
    if operation == "write":
        text = json.dumps(payload["value"], sort_keys=True, indent=1) + "\n"
        if len(text.encode()) > LIMIT:
            raise ValueError("publication exceeds 32 MiB")
        write_text(Path(payload["path"]), text)
        for name in payload.get("cleanup", []):
            Path(name).unlink(missing_ok=True)
        return {}
    if operation == "collect":
        from _screen_collect import collect

        return collect(payload)

    raise ValueError(f"unknown screen phase: {operation}")


if __name__ == "__main__":
    raw = sys.stdin.buffer.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("phase input exceeds 32 MiB")
    print(json.dumps(execute(sys.argv[1], json.loads(raw)), sort_keys=True))
