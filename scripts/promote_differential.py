"""Author a regression test from a reproduced finding and an explicit expectation."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import write_text
from _reference_process import run
from _reference_process import run as run_formatter
from _replay_evidence import command as replay_command
from _replay_evidence import parameters
from _screen_evidence import LIMIT, read
from _screen_payload import finding
from differential import SPECS, Outcome, _case_load, run_ours, run_ours_fast


def main() -> None:
    """Confirm the cause before writing a standalone pytest regression."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("finding", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--expected-side", choices=("ours", "ref"), required=True)
    parser.add_argument(
        "--reason", required=True, help="why this expectation is correct"
    )
    parser.add_argument("--allow-drift", action="store_true")
    parser.add_argument("--ref", help="replacement reference command after relocation")
    args = parser.parse_args()
    if not args.reason.strip():
        parser.error("expectation reason must not be blank")
    value = read(args.finding)
    finding(value)
    command = replay_command(
        value, args.finding, allow_drift=args.allow_drift, reference=args.ref
    )
    key = next(
        name for name, spec in SPECS.items() if spec.language == value["language"]
    )
    spec = SPECS[key]
    params = parameters(value)
    bound = sum(
        params[name] for name in ("budget_seconds", "setup_seconds", "finalize_seconds")
    )
    code, output, _error, status = run(command, b"", bound + 1)
    observations = [
        json.loads(line)
        for line in output.splitlines()
        if line.startswith(b'{"expected_cause"')
    ]
    if (
        status is not None
        or code != 1
        or len(observations) != 1
        or observations[0].get("verdict") != "reproduced"
    ):
        parser.error("finding must reproduce with a definitive verdict")
    observed = _case_load(observations[0]["observed"])
    case = value["minimized"] or value["original"]
    if (observed.program, observed.stdin, observed.cause) != (
        case["program"],
        case["stdin"],
        case["cause"],
    ):
        parser.error("replay does not match the selected finding")
    outcome = getattr(observed, args.expected_side)
    if outcome.status not in {"halt", "eof", "error"}:
        parser.error("regression expectation must be a terminating outcome")
    if args.destination.exists():
        parser.error("destination already exists")
    payload = {
        "finding_sha256": hashlib.sha256(
            json.dumps(value, sort_keys=True).encode()
        ).hexdigest(),
        "expected_side": args.expected_side,
        "reason": args.reason,
        "identity": value.get("identity"),
        "replay_provenance": observations[0].get("provenance"),
        "language": key,
        "program": case["program"],
        "stdin": case["stdin"],
        "steps": spec.max_steps,
        "status": outcome.status,
        "output": observations[0]["observed"][args.expected_side]["output"],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    literals = "\n".join(
        "    " + repr(encoded[i : i + 32]) for i in range(0, len(encoded), 32)
    )
    text = (
        '"""Regression promoted from a confirmed differential finding."""\n\n'
        "import base64\nimport json\n\n"
        "from scripts.promote_differential import regression_outcomes\n\n"
        "CASE = json.loads(\n" + literals + "\n)\n\n\n"
        "def test_promoted_finding():\n"
        '    """Pin the explicitly selected outcome on each execution path."""\n'
        '    outcomes = regression_outcomes(CASE["language"], CASE["program"], '
        'CASE["stdin"], CASE["steps"])\n'
        "    for outcome in outcomes:\n"
        '        assert (outcome.status, outcome.output) == (CASE["status"], '
        'base64.b64decode(CASE["output"])), outcomes\n'
    )
    code, formatted, error, status = run_formatter(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--stdin-filename",
            str(args.destination),
        ],
        text.encode(),
        5,
        LIMIT,
    )
    if status is not None or code != 0:
        parser.error(
            "regression formatting failed: " + error.decode("utf-8", "replace")
        )
    write_text(args.destination, formatted.decode())


def regression_outcomes(
    key: str, program: str, stdin: str, steps: int
) -> list[Outcome]:
    """Execute the comparison adapter and applicable public execution path."""
    spec = SPECS[key]
    ours = (spec.ours or run_ours)(spec.language, program, stdin, steps)
    return [ours] if spec.ours else [ours, run_ours_fast(spec.language, program, stdin)]


if __name__ == "__main__":
    main()
