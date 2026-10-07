"""Measure Vandevelo identifier and sampled-fallback work; execute one naming rule."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from random import Random
from time import process_time
from types import FrameType
from typing import Any

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.vandevelo import _Machine
from esolangs.vm import run_until_halt_or_cycle

_MODULE = importlib.import_module("esolangs.tools.vandevelo")
_NAMES = re.compile(r"[A-Za-z0-9_&*$]+")
_RESERVED = {"Inp", "Nil", "loop", "l"}
_LAST_DRAW: list[object] = [None]


@dataclass
class Work:
    """Exact call counts and element visits, excluding timing conclusions."""

    fallback_calls: int = 0
    pair_draws: int = 0
    draw_visits: int = 0


def _profile(frame: FrameType, event: str, _arg: Any, work: Work) -> None:
    if event != "call":
        return
    caller = frame.f_back
    if caller is None:
        return
    fallback = _MODULE._ensure_popular.__code__  # noqa: SLF001
    if frame.f_code is _MODULE._pairs.__code__ and caller.f_code is fallback:  # noqa: SLF001
        # Each sampling call lists its cosets afresh; holding the list keeps
        # its identity from being reused by a later call.
        if caller.f_locals["reps"] is not _LAST_DRAW[0]:
            _LAST_DRAW[0] = caller.f_locals["reps"]
            work.fallback_calls += 1
        work.pair_draws += 1
        work.draw_visits += len(frame.f_locals["node"].reps)


def frequency_names(program: str) -> str:
    """Assign shortest existing names to most frequent identifiers, simultaneously."""
    counts = Counter(name for name in _NAMES.findall(program) if name not in _RESERVED)
    ranked = sorted(counts, key=lambda name: (-counts[name], name))
    shortest = sorted(counts, key=lambda name: (len(name), name))
    rename = dict(zip(ranked, shortest, strict=True))
    return _NAMES.sub(lambda match: rename.get(match[0], match[0]), program)


def measure(table: str) -> tuple[str, dict[str, int]]:
    """Return generated source and its identifier/fallback costs without mutation."""
    work = Work()
    prior = sys.getprofile()
    try:
        sys.setprofile(lambda frame, event, arg: _profile(frame, event, arg, work))
        source = _MODULE.vandevelo(table)
    finally:
        sys.setprofile(prior)
    names = [name for name in _NAMES.findall(source) if name not in _RESERVED]
    renamed = frequency_names(source)
    return source, {
        **asdict(work),
        "characters": len(source),
        "identifier_characters": sum(map(len, names)),
        "identifier_occurrences": len(names),
        "renamed_characters": len(renamed),
    }


def execute(
    source: str,
    table: str,
    *,
    max_rows: int | None = None,
    cpu_deadline: float | None = None,
) -> int:
    """Check every row by proved halt or cycle, refusing an unsettled run."""
    n = len(table).bit_length() - 1
    count = len(table) if max_rows is None else min(max_rows, len(table))
    rows = (
        range(len(table))
        if count == len(table)
        else (index * (len(table) - 1) // max(1, count - 1) for index in range(count))
    )
    for row in rows:
        if cpu_deadline is not None and process_time() >= cpu_deadline:
            raise SystemExit("CPU ceiling reached; remaining rows unverified")
        bits = format(row, f"0{n}b")
        machine = _Machine(source, ScriptedIO("".join(f"{bit}\n" for bit in bits)))
        answer = "0" if run_until_halt_or_cycle(machine, limit=100_000) else "1"
        if answer != table[row]:
            raise AssertionError(f"wrong answer at row {row}: {answer} != {table[row]}")
    return count


def positive_control() -> Work:
    """Force the sampled fallback on a span-invariant set; verify the chosen count."""
    # Six-input span {0,1,2,3} over three cosets; no candidate is scored yet.
    points = {base ^ offset for base in (0, 4, 8) for offset in range(4)}
    node = _MODULE._Node.root(points).below(1).below(2)  # noqa: SLF001
    work = Work()
    prior = sys.getprofile()
    try:
        sys.setprofile(lambda frame, event, arg: _profile(frame, event, arg, work))
        _MODULE._ensure_popular(node, 6)  # noqa: SLF001
    finally:
        sys.setprofile(prior)
    direction, count = _MODULE._best(node)  # noqa: SLF001
    assert direction is not None
    assert count == 8
    assert count == sum((point ^ direction) in points for point in points)
    assert work.fallback_calls == 1
    assert 1 <= work.pair_draws <= _MODULE._SAMPLES  # noqa: SLF001
    # A draw visits the three cosets, not the twelve points.
    assert work.draw_visits == 3 * work.pair_draws
    return work


def main() -> int:
    """Run a bounded corpus and compare a named rule, never an enumeration search."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-inputs", type=int, default=6, choices=range(1, 13))
    parser.add_argument("--min-inputs", type=int, default=1, choices=range(1, 13))
    parser.add_argument("--random-cases", type=int, default=8, choices=range(9))
    parser.add_argument("--sample-rows", type=int)
    parser.add_argument("--cpu-seconds", type=float, default=30)
    args = parser.parse_args()
    if not 0 < args.cpu_seconds <= 60:
        parser.error("--cpu-seconds must be in (0, 60]")
    if args.min_inputs > args.max_inputs:
        parser.error("--min-inputs exceeds --max-inputs")
    if args.sample_rows is not None and args.sample_rows <= 0:
        parser.error("--sample-rows must be positive")
    started = process_time()
    print(json.dumps({"positive_control": asdict(positive_control())}), flush=True)
    rng = Random(0)
    for n in range(args.min_inputs, args.max_inputs + 1):
        tables = [
            "0" * (1 << n),
            "1" * (1 << n),
            "".join(str(row.bit_count() & 1) for row in range(1 << n)),
        ]
        tables.extend(
            "".join(rng.choice("01") for _ in range(1 << n))
            for _ in range(args.random_cases)
        )
        for index, table in enumerate(tables):
            if process_time() - started >= args.cpu_seconds:
                raise SystemExit("CPU ceiling reached; remaining cases unverified")
            source, costs = measure(table)
            rows = execute(
                source,
                table,
                max_rows=args.sample_rows,
                cpu_deadline=started + args.cpu_seconds,
            )
            rows += execute(
                frequency_names(source),
                table,
                max_rows=args.sample_rows,
                cpu_deadline=started + args.cpu_seconds,
            )
            print(
                json.dumps(
                    {"inputs": n, "case": index, "executed_rows": rows, **costs}
                ),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
