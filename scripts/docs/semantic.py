"""Language-owned semantic admission records and executed fault controls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from verify.process import stop_process_tree  # noqa: E402

from .fragments import section  # noqa: E402


@dataclass(frozen=True)
class Evidence:
    """Declare the bounded checks and the contract whose choices they exercise."""

    kind: str
    contract: str
    tests: tuple[str, ...]


def parse(language: str, data: dict[str, Any]) -> Evidence:
    """Reject missing, foreign, or unbounded admission records."""
    from esolangs.registry import LANGUAGES

    owner = Path("src/esolangs/languages") / LANGUAGES[language].id
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("semantic evidence needs version = 1")
    if set(data) != {"version", "kind", "contract", "tests"}:
        raise ValueError("semantic evidence needs kind, contract and tests")
    if not isinstance(data["kind"], str) or data["kind"] not in {"model", "examples"}:
        raise ValueError("semantic evidence kind must be model or examples")
    contract = data["contract"]
    if not isinstance(contract, str) or contract not in {
        "interpreter.py",
        "interpreter/__init__.py",
    }:
        raise ValueError("semantic evidence must name its interpreter contract")
    if not (ROOT / owner / contract).is_file() or ".." in Path(contract).parts:
        raise ValueError("semantic contract must be an owned source file")
    tests = data["tests"]
    if (
        not isinstance(tests, list)
        or not tests
        or not all(isinstance(t, str) for t in tests)
    ):
        raise ValueError("semantic evidence needs nonempty pytest node ids")
    if len(set(tests)) != len(tests):
        raise ValueError("semantic evidence repeats a check")
    for node in tests:
        path, *selectors = node.split("::")
        target = Path(path)
        if (
            not selectors
            or not target.is_relative_to(owner / "tests")
            or ".." in target.parts
            or not (ROOT / target).is_file()
        ):
            raise ValueError(
                "semantic checks must name owned test functions or classes"
            )
    return Evidence(data["kind"], contract, tuple(tests))


def load(language: str) -> Evidence:
    """Load the language's declared semantic checks."""
    from esolangs.registry import LANGUAGES

    path = ROOT / "src/esolangs/languages" / LANGUAGES[language].id / "language.toml"
    return parse(language, section(path, "semantic_evidence") or {})


def verify(language: str, scratch: Path) -> tuple[int, int]:
    """Require clean checks and an assertion detecting an actually injected fault."""
    record = load(language)
    start = time.monotonic()
    scratch.mkdir(parents=True, exist_ok=True)
    env = os.environ | {"PYTHONPATH": str(ROOT / "src"), "PYTEST_ADDOPTS": ""}
    env.pop("PYTEST_CURRENT_TEST", None)
    log = scratch / "probe.json"
    request = json.dumps(
        {
            "language": language,
            "kind": record.kind,
            "contract": record.contract,
            "tests": record.tests,
            "faults": [False, True],
        }
    )
    with log.open("w") as output:
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/semantic_probe.py")],
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            process.communicate(
                request, timeout=max(0.01, 60 - (time.monotonic() - start))
            )
        except subprocess.TimeoutExpired as error:
            stop_process_tree(process)
            raise AssertionError(
                f"{language}: semantic checks exceeded 60s; {log}"
            ) from error
    try:
        reports = json.loads(log.read_text())
    except (ValueError, OSError) as error:
        raise AssertionError(
            f"{language}: invalid semantic probe report; {log}"
        ) from error
    assert process.returncode == 0, (language, reports)
    baseline, faulted = reports
    assert baseline["status"] == 0, (language, "baseline", baseline)
    assert baseline["passed"] > 0, (language, "no checks executed", baseline)
    assert baseline["other"] == 0, (language, "baseline errors or skips", baseline)
    assert baseline["assertions"] == 0, (language, "baseline assertions", baseline)
    assert faulted["status"] == 1, (language, "undetected output fault", faulted)
    assert faulted["hits"] > 0, (language, "fault never exercised", faulted)
    assert faulted["assertions"] > 0, (
        language,
        "no assertion detected the fault",
        faulted,
    )
    return baseline["passed"], faulted["assertions"]
