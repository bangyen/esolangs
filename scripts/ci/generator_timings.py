"""Report generator timing changes within matching environments and corpora.

Run after check_generator_sizes.py --timings. History keeps eight successful
runs; two successive increases of at least 20% over the earlier median are
reported as persistent. Timing changes never fail the correctness gate.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

ENVIRONMENT = ("python", "platform", "machine", "harness")


def snapshot(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate executed measurements and retain comparable timing fields."""
    if not records:
        raise ValueError("empty timing corpus")
    environment = {key: records[0]["provenance"][key] for key in ENVIRONMENT}
    timings = {}
    controls = {}
    for row in records:
        if {key: row["provenance"][key] for key in ENVIRONMENT} != environment:
            raise ValueError("mixed timing environments")
        if any(item["matches"] is not True for item in row.get("executions", [row])):
            raise ValueError("unsuccessful execution")
        key = json.dumps([row["language"], row["truth_table"]])
        value = row["generation_ns_median"]
        if (
            key in timings
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError("duplicate control or invalid timing")
        timings[key] = value
        controls[key] = {
            field: row[field]
            for field in ("schema", "track_store", "step_cap", "timeout")
        }
    return {"environment": environment, "controls": controls, "timings": timings}


def compare(
    current: dict[str, Any], history: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """Return a Markdown report and history containing only the matching cohort."""
    # A restored history can hold entries this snapshot shape predates or
    # entries written by a differently shaped run (the 2026-11-02 weekly
    # restored a list entry and crashed here).  History is advisory --
    # timing changes never fail the gate -- so drop malformed entries
    # instead of crashing on them.
    matching = [
        run
        for run in history
        if isinstance(run, dict)
        and all(
            isinstance(run.get(key), dict)
            for key in ("environment", "controls", "timings")
        )
        and all(run[key] == current[key] for key in ("environment", "controls"))
    ]
    lines = ["### Generator timing comparison", ""]
    if not matching:
        lines.append("New environment or corpus; recorded the first reference run.")
    else:
        references = matching[:-1] or matching

        def priority(item: tuple[str, float]) -> tuple[bool, float, str]:
            key, value = item
            baseline = statistics.median(run["timings"][key] for run in references)
            persistent = (
                len(matching) >= 2 and matching[-1]["timings"][key] / baseline >= 1.2
            )
            return (not persistent, -value / baseline, key)

        for key, value in sorted(current["timings"].items(), key=priority):
            baseline = statistics.median(run["timings"][key] for run in references)
            ratio = value / baseline
            if ratio >= 1.2:
                persistent = (
                    len(matching) >= 2
                    and matching[-1]["timings"][key] / baseline >= 1.2
                )
                language, table = json.loads(key)
                status = "persistent" if persistent else "candidate"
                lines.append(
                    f"- {language} `{table}`: +{(ratio - 1) * 100:.1f}% ({status}); "
                    f"median {value / 1e6:.3f} ms, "
                    f"reference {baseline / 1e6:.3f} ms."
                )
        if len(lines) == 2:
            lines.append("No generation timing increases of at least 20%.")
    return "\n".join(lines) + "\n", [*matching, current][-8:]


def main() -> None:
    """Read an executed sweep, append history, and write the comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    current = snapshot(json.loads(args.measurements.read_text(encoding="utf-8")))
    history = (
        json.loads(args.history.read_text(encoding="utf-8"))
        if args.history.exists()
        else []
    )
    if not isinstance(history, list):
        history = []
    report, updated = compare(current, history)
    args.report.write_text(report, encoding="utf-8")
    args.history.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    print(report, end="")


if __name__ == "__main__":
    main()
