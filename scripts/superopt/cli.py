"""Command line: ``control``, ``novel``, ``certify`` and the v2 audit.

Run from the repo root with ``PYTHONPATH=src:scripts``:

- ``python -m superopt control`` -- the positive control: rediscover
  the digits gadget's suffix and prove nothing shorter is injective.
- ``python -m superopt novel`` -- search the whole gadget from zeroed
  cells over the full alphabet, below the shipped 16 ops.
- ``python -m superopt certify {suffix|full} TOKEN...`` -- certify one
  program against a spec, exactly, over the full table.
- ``python -m superopt audit-one FALSE`` -- the v2 small-end audit of
  one language at one arity (see :mod:`superopt.audit`).
- ``python -m superopt audit-fleet --arity 1`` -- the audit across
  the Boolean fleet, cheapest first, inside a global CPU budget;
  writes a JSON record per language to ``--out``.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .audit import Corpus, Outcome, Runner, audit_fleet, audit_language
from .machine import FULL_ALPHABET, SUFFIX_ALPHABET
from .search import Stats, certify, search, search_bfs
from .targets import SHIPPED_GADGET, SHIPPED_SUFFIX, full_spec, suffix_spec


def _control(max_length: int) -> int:
    spec = suffix_spec()
    stats = Stats()
    result = search(spec, SUFFIX_ALPHABET, max_length, stats)
    print(
        f"candidates evaluated: {stats.candidates}; "
        f"rows evaluated: {stats.rows_evaluated}"
    )
    if result.length is None:
        print(f"no injective suffix up to length {max_length}")
        return 1
    print(f"first injective length: {result.length}; hits: {len(result.hits)}")
    ok = result.hits == (SHIPPED_SUFFIX,)
    for hit in result.hits:
        certified = certify(hit, spec)
        ok = ok and certified
        print(f"  {' '.join(hit)}  certified: {certified}")
    print(f"control {'passed' if ok else 'FAILED'}")
    return 0 if ok else 1


def _novel(max_depth: int, node_cap: int, budget_seconds: float) -> int:
    spec = full_spec()
    result = search_bfs(
        spec,
        FULL_ALPHABET,
        max_depth,
        node_cap=node_cap,
        budget_seconds=budget_seconds,
    )
    for depth, size in enumerate(result.levels):
        print(f"depth {depth}: {size} signatures")
    if result.program is None:
        print(
            f"no injective program up to depth {result.exhausted}"
            f" (shipped: {len(SHIPPED_GADGET)} ops)"
            f"{'; stopped by cap/budget' if result.capped else ''}"
        )
        return 0
    certified = certify(result.program, spec)
    print(
        f"hit at {len(result.program)} ops (shipped: {len(SHIPPED_GADGET)}):"
        f" {' '.join(result.program)}  certified: {certified}"
    )
    return 0 if certified else 1


def _certify(target: str, program: tuple[str, ...]) -> int:
    spec = suffix_spec() if target == "suffix" else full_spec()
    certified = certify(program, spec)
    print(f"{' '.join(program)}  certified: {certified}")
    return 0 if certified else 1


def _record(
    name: str, corpus: Corpus, outcomes: list[Outcome], runner: Runner
) -> dict[str, Any]:
    """One language's audit record, JSON-ready (huge spaces as text)."""
    rows = []
    for outcome in outcomes:
        row = asdict(outcome)
        if row["space"] > 10**15:
            row["space"] = f"~1e{len(str(row['space'])) - 1}"
        rows.append(row)
    return {
        "language": name,
        "alphabet": "".join(corpus.alphabet),
        "alphabet_size": len(corpus.alphabet),
        "corpus_arities": list(corpus.corpus_arities),
        "corpus_truncated": corpus.truncated,
        "parameterized": runner.parameterized,
        "terminating": runner.terminating,
        "outcomes": rows,
    }


def _print_outcomes(outcomes: list[Outcome]) -> None:
    for o in outcomes:
        line = (
            f"  table {o.table}: shipped {o.shipped_size} -> {o.outcome}"
            f"  [{o.candidates:,} candidates, {o.rows:,} rows, {o.seconds:.1f}s]"
        )
        if o.found is not None:
            line += f"  found {o.found!r} ({len(o.found)} chars)"
        if o.note:
            line += f"  -- {o.note}"
        print(line)


def _audit_one(args: argparse.Namespace) -> int:
    corpus, outcomes = audit_language(
        args.language,
        args.arity,
        candidate_cap=args.cap,
        wall_seconds=args.wall,
    )
    print(
        f"{args.language} at n={args.arity}: alphabet "
        f"{len(corpus.alphabet)} chars {''.join(corpus.alphabet)!r} "
        f"from corpus arities {corpus.corpus_arities}"
    )
    _print_outcomes(outcomes)
    return 0


def _audit_fleet(args: argparse.Namespace) -> int:
    from esolangs.languages.generators import BOOLEAN

    names = sorted(BOOLEAN)
    if args.names:
        wanted = {part.strip() for part in args.names.split(",")}
        names = [n for n in names if n in wanted]
    began = time.monotonic()
    results = audit_fleet(
        names,
        args.arity,
        budget_seconds=args.budget,
        candidate_cap=args.cap,
        wall_seconds=args.wall,
        progress=True,
    )
    records = []
    gaps = 0
    for name, corpus, outcomes in results:
        records.append(_record(name, corpus, outcomes, Runner(name)))
        gaps += sum(1 for o in outcomes if o.outcome == "gap")
    Path(args.out).write_text(json.dumps(records, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for record in records:
        for row in record["outcomes"]:
            counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
    print(
        f"fleet n={args.arity}: {len(records)} languages, outcomes {counts}, "
        f"{gaps} gaps, {time.monotonic() - began:.0f}s wall; wrote {args.out}"
    )
    for record in records:
        for row in record["outcomes"]:
            if row["outcome"] == "gap":
                print(
                    f"  GAP {record['language']} table {row['table']}: "
                    f"shipped {row['shipped_size']} -> {row['found']!r}"
                )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch one superoptimizer command."""
    parser = argparse.ArgumentParser(prog="superopt")
    commands = parser.add_subparsers(dest="command", required=True)
    control = commands.add_parser("control")
    control.add_argument("--max-length", type=int, default=6)
    novel = commands.add_parser("novel")
    novel.add_argument("--max-depth", type=int, default=15)
    novel.add_argument("--node-cap", type=int, default=2_000_000)
    novel.add_argument("--budget-seconds", type=float, default=1500.0)
    cert = commands.add_parser("certify")
    cert.add_argument("target", choices=("suffix", "full"))
    cert.add_argument("program", nargs="+")
    one = commands.add_parser("audit-one")
    one.add_argument("language")
    one.add_argument("--arity", type=int, default=1)
    one.add_argument("--cap", type=int, default=None)
    one.add_argument("--wall", type=float, default=900.0)
    fleet = commands.add_parser("audit-fleet")
    fleet.add_argument("--arity", type=int, default=1)
    fleet.add_argument("--budget", type=float, default=1500.0)
    fleet.add_argument("--cap", type=int, default=150_000)
    fleet.add_argument("--wall", type=float, default=90.0)
    fleet.add_argument("--names", default=None)
    fleet.add_argument("--out", default="notes/audit-fleet.json")
    args = parser.parse_args(argv)
    if args.command == "control":
        return _control(args.max_length)
    if args.command == "novel":
        return _novel(args.max_depth, args.node_cap, args.budget_seconds)
    if args.command == "audit-one":
        return _audit_one(args)
    if args.command == "audit-fleet":
        return _audit_fleet(args)
    return _certify(args.target, tuple(args.program))
