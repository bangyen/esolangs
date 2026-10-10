"""Rotate two mutation targets with a four-minute process-tree budget each."""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECONDS_PER_TARGET = 240
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import write_text  # noqa: E402
from _mutation_evidence import provenance, validate  # noqa: E402
from _verify_process import stop_process_tree  # noqa: E402


def _rotation(kind: str) -> list[str]:
    """Each language's target of ``kind`` its ``weekly_mutation`` names."""
    sys.path.insert(0, str(ROOT / "src"))
    from esolangs.registry import LANGUAGES

    return [
        name
        if kind == "interpreter"
        else lang.boolean.__module__.removeprefix("esolangs.").replace(".", "/")
        for name, lang in LANGUAGES.items()
        if kind in lang.weekly_mutation and (kind != "generator" or lang.boolean)
    ]


def targets_for(date: datetime.date) -> tuple[str, str]:
    """Return the pair for an absolute week, including across year boundaries.

    Each rotation is read from the registry, so a removed language drops out.
    """
    week = date.toordinal() // 7
    interpreters, generators = _rotation("interpreter"), _rotation("generator")
    return interpreters[week % len(interpreters)], generators[week % len(generators)]


def run_target(kind: str, target: str, output: Path) -> bool:
    """Save score, log and inspection files; fail on timeout or harness error."""
    output.mkdir(parents=True, exist_ok=True)
    (output / "score.json").unlink(missing_ok=True)
    work = output / "work"
    work.mkdir(exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "mutate.py"),
        kind,
        target,
        "--jobs",
        "2",
        "--keep",
        "--report",
        str(output / "score.json"),
    ]
    if kind == "generator":
        command.append("--focused")
    evidence = provenance()
    started = time.monotonic()
    with (output / "run.log").open("w") as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, "TMPDIR": str(work), "PYTHONUNBUFFERED": "1"},
            start_new_session=os.name == "posix",
        )
        timed_out = False
        try:
            code = process.wait(timeout=SECONDS_PER_TARGET)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_process_tree(process)
            code = process.returncode
        except BaseException:
            stop_process_tree(process)
            write_text(
                output / "status.json",
                json.dumps(
                    {
                        "kind": kind,
                        "target": target,
                        "status": "interrupted",
                        "provenance": evidence,
                    }
                )
                + "\n",
            )
            raise
    complete = not timed_out and code == 0 and (output / "score.json").exists()
    validation_error = None
    if complete:
        try:
            validate(output / "score.json", kind, target, evidence)
        except (OSError, ValueError) as error:
            complete = False
            validation_error = str(error)
    status = "complete" if complete else "timeout" if timed_out else "failed"
    write_text(
        output / "status.json",
        json.dumps(
            {
                "kind": kind,
                "target": target,
                "status": status,
                "returncode": code,
                "validation_error": validation_error,
                "seconds": time.monotonic() - started,
                "provenance": evidence,
            },
            indent=2,
        )
        + "\n",
    )
    print(f"{kind} {target}: {status}", flush=True)
    return complete


def main() -> int:
    """Run this week's pair and retain evidence even on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    interpreter, generator = targets_for(datetime.datetime.now(datetime.UTC).date())
    output = args.output.resolve()
    results = [
        run_target("interpreter", interpreter, output / "interpreter"),
        run_target("generator", generator, output / "generator"),
    ]
    return int(not all(results))


if __name__ == "__main__":
    raise SystemExit(main())
