"""Report generation slowdowns sustained across two weekly sweeps; never gate."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _verify_process import write_text

Key = tuple[str, str]


def samples(records: list[dict[str, Any]]) -> dict[Key, int]:
    """Index positive best-of-repeat timings by language and exact table."""
    result = {}
    for record in records:
        key = (record["language"], record["truth_table"])
        value = record["generation_ns_best"]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"invalid generation timing for {key}")
        if key in result:
            raise ValueError(f"duplicate timing for {key}")
        result[key] = value
    return result


def report(
    current: list[dict[str, Any]],
    history: list[list[dict[str, Any]]],
    *,
    ratio: float = 1.5,
    floor_ns: int = 10_000_000,
) -> str:
    """Compare the latest two sweeps with their predecessor, above a noise floor."""
    if not math.isfinite(ratio) or ratio <= 1 or floor_ns < 0:
        raise ValueError("ratio must exceed 1 and floor_ns must be non-negative")
    now = samples(current)
    if len(history) < 2:
        return "Generator timings: collecting history (three sweeps required).\n"

    def cohort(run: list[dict[str, Any]]) -> set[str]:
        return {
            json.dumps(
                [
                    record.get("schema"),
                    *(
                        record.get("provenance", {}).get(key)
                        for key in ("python", "platform", "machine", "harness")
                    ),
                ]
            )
            for record in run
        }

    if any(
        not all(
            record.get("provenance", {}).get(key)
            for key in ("python", "platform", "machine", "harness")
        )
        for run in [current, *history[-2:]]
        for record in run
    ):
        return "Generator timings: missing environment evidence; collecting history.\n"
    environment = cohort(current)
    if len(environment) != 1 or any(cohort(run) != environment for run in history[-2:]):
        return (
            "Generator timings: incompatible environments; "
            "collecting comparable history.\n"
        )
    before, previous = (samples(run) for run in history[-2:])
    common = before.keys() & previous.keys() & now.keys()
    regressions = []
    for language, table in sorted(common):
        key = (language, table)
        base, last, latest = before[key], previous[key], now[key]
        if base >= floor_ns and min(last, latest) >= ratio * base:
            regressions.append(
                f"- {language}, {len(table).bit_length() - 1} inputs: "
                f"{base / 1e6:.2f} ms → {last / 1e6:.2f} ms → "
                f"{latest / 1e6:.2f} ms ({latest / base:.2f}x)."
            )
    heading = (
        f"Generator timings: {len(common)} comparable cases; "
        f"{len(now.keys() - common)} cases lack comparable history.\n"
    )
    if regressions:
        return (
            heading
            + "\nSustained slowdowns (investigate with just benchmark):\n\n"
            + "\n".join(regressions)
            + "\n"
        )
    return heading + "No sustained slowdowns above the noise floor.\n"


def main(argv: list[str] | None = None) -> int:
    """Append a sweep to a bounded history and emit a non-blocking report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("current", type=Path)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)
    current = json.loads(args.current.read_text(encoding="utf-8"))
    history = (
        json.loads(args.history.read_text(encoding="utf-8"))
        if args.history.exists()
        else []
    )
    summary = report(current, history)
    print(summary, end="")
    if args.summary is not None:
        with args.summary.open("a", encoding="utf-8") as stream:
            stream.write(summary)
    args.history.parent.mkdir(parents=True, exist_ok=True)
    write_text(args.history, json.dumps([*history[-1:], current]) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
