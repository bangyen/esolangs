"""Author a regression test from a reproduced finding and an explicit expectation."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import write_text
from _reference_process import run
from _screen_evidence import read
from _screen_payload import finding
from differential import SPECS, Outcome, _case_load, run_ours, run_ours_fast


def main() -> None:
    """Confirm the cause before writing a standalone pytest regression."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("finding", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--expected-side", choices=("ours", "ref"), required=True)
    args = parser.parse_args()
    value = read(args.finding)
    finding(value)
    command = value["replay"]
    key = next(
        name for name, spec in SPECS.items() if spec.language == value["language"]
    )
    spec = SPECS[key]
    bound = sum(
        float(command[command.index(flag) + 1])
        for flag in ("--budget-seconds", "--setup-seconds", "--finalize-seconds")
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
    text = (
        '"""Regression promoted from a confirmed differential finding."""\n\n'
        "from scripts.promote_differential import regression_outcomes\n\n\n"
        "def test_promoted_finding():\n"
        f"    outcomes = regression_outcomes({key!r}, {case['program']!r}, "
        f"{case['stdin']!r}, {spec.max_steps!r})\n"
        "    for outcome in outcomes:\n"
        f"        assert (outcome.status, outcome.output) == "
        f"({outcome.status!r}, {outcome.output!r}), outcomes\n"
    )
    write_text(args.destination, text)


def regression_outcomes(
    key: str, program: str, stdin: str, steps: int
) -> list[Outcome]:
    """Execute the comparison adapter and applicable public execution path."""
    spec = SPECS[key]
    ours = (spec.ours or run_ours)(spec.language, program, stdin, steps)
    return [ours] if spec.ours else [ours, run_ours_fast(spec.language, program, stdin)]


if __name__ == "__main__":
    main()
