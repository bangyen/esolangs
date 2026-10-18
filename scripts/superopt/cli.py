"""Command line: ``control``, ``novel`` and ``certify``.

Run from the repo root with ``PYTHONPATH=src:scripts``:

- ``python -m superopt control`` -- the positive control: rediscover
  the digits gadget's suffix and prove nothing shorter is injective.
- ``python -m superopt novel`` -- search the whole gadget from zeroed
  cells over the full alphabet, below the shipped 16 ops.
- ``python -m superopt certify {suffix|full} TOKEN...`` -- certify one
  program against a spec, exactly, over the full table.
"""

from __future__ import annotations

import argparse

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
    args = parser.parse_args(argv)
    if args.command == "control":
        return _control(args.max_length)
    if args.command == "novel":
        return _novel(args.max_depth, args.node_cap, args.budget_seconds)
    return _certify(args.target, tuple(args.program))
