"""Rotate two mutation targets with a four-minute process-tree budget each."""

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ("Qoibl", "tools/nocomment"),
    ("brainfuck", "tools/smallfuck"),
    ("Bitdeque", "tools/suffolk"),
    ("Smallfuck", "tools/underload"),
    ("Line", "tools/piet"),
    ("Piet", "tools/line"),
)
SECONDS_PER_TARGET = 240


def _present(kind: str, target: str) -> bool:
    """Whether the pair's language and generator module are both still here."""
    sys.path.insert(0, str(ROOT / "src"))
    from esolangs.registry import LANGUAGES

    module = ROOT / "src/esolangs" / target
    return kind in LANGUAGES and (
        module.with_suffix(".py").is_file() or (module / "__init__.py").is_file()
    )


def targets_for(date: datetime.date) -> tuple[str, str]:
    """Return the pair for an absolute week, including across year boundaries.

    A pair whose language was removed drops out of the rotation.
    """
    targets = [pair for pair in TARGETS if _present(*pair)]
    return targets[(date.toordinal() // 7) % len(targets)]


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
    started = time.monotonic()
    with (output / "run.log").open("w") as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "TMPDIR": str(work), "PYTHONUNBUFFERED": "1"},
            start_new_session=True,
        )
        timed_out = False
        try:
            code = process.wait(timeout=SECONDS_PER_TARGET)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    complete = not timed_out and code == 0 and (output / "score.json").exists()
    status = "complete" if complete else "timeout" if timed_out else "failed"
    (output / "status.json").write_text(
        json.dumps(
            {
                "kind": kind,
                "target": target,
                "status": status,
                "returncode": code,
                "seconds": time.monotonic() - started,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"{kind} {target}: {status}", flush=True)
    return complete


def main() -> int:
    """Run this week's pair on POSIX and retain evidence even on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("process-tree budgets require POSIX")
    interpreter, generator = targets_for(datetime.datetime.now(datetime.UTC).date())
    output = args.output.resolve()
    results = [
        run_target("interpreter", interpreter, output / "interpreter"),
        run_target("generator", generator, output / "generator"),
    ]
    return int(not all(results))


if __name__ == "__main__":
    raise SystemExit(main())
