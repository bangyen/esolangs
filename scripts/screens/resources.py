"""Execute every row of bounded constant, parity and seeded dense tables."""

import argparse
import json
import random
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _budget import completed, options, supervise
from _screen_evidence import case_id, reused
from benchmark import measure


def corpus(n: int) -> dict[str, str]:
    """Return four reproducible tables without searching."""
    width = 1 << n
    rng = random.Random(n)
    return {
        "zero": "0" * width,
        "one": "1" * width,
        "parity": "".join(str(row.bit_count() % 2) for row in range(width)),
        "dense": f"{rng.getrandbits(width):0{width}b}",
    }


def audit(
    language: str,
    n: int,
    table: str,
    bounds: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, int | str]:
    """Check answers, and ``bounds`` if given; report exposed VM store lengths.

    ``bounds(profile)`` asserts a language's construction bounds on the
    returned profile; each language's own tests hold its bounds.
    """
    result = measure(
        language,
        table,
        repeat=1,
        row=0,
        # Generous for every audited shape: a table scan or a fixed leaf.
        step_cap=max(64 * len(table) + 64 * n + 512, 100 * n + 8192),
        all_rows=True,
        timeout=30,
        track_store=True,
    )
    if not all(item["matches"] is True for item in result["executions"]):
        raise ValueError(f"{language} n={n}: wrong or undecided row")
    commands = result["worst_row_commands"]
    memory = max(item["peak_memory_cells"] for item in result["executions"])
    stack = max(item["peak_stack_items"] for item in result["executions"])
    payload = {
        key: max(item[key] for item in result["executions"])
        for key in (
            "peak_control_stack_items",
            "peak_data_bits",
            "peak_control_stack_bits",
            "peak_integer_bits",
            "peak_pc_bits",
            "peak_machine_bits",
        )
    }
    profile: dict[str, int | str] = {
        "language": language,
        "inputs": n,
        "source_units": result["source_units"],
        "source_utf8_bits": result["source_utf8_bits"],
        "worst_row_commands": commands,
        "peak_memory_cells": memory,
        "peak_stack_items": stack,
        **payload,
    }
    if bounds is not None:
        bounds(profile)
    return profile


def main() -> None:
    """Print resource profiles through a bounded arity, every answer checked."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-inputs", type=int, default=8)
    parser.add_argument("languages", nargs="*")
    options(parser)
    args = parser.parse_args()
    if not 1 <= args.max_inputs <= 10:
        parser.error("--max-inputs must be between 1 and 10")
    from esolangs.registry import LANGUAGES, resolve

    languages = (
        [resolve(name) for name in args.languages]
        if args.languages
        else [name for name, lang in LANGUAGES.items() if lang.payload]
    )
    if any(not LANGUAGES[name].payload for name in languages):
        parser.error("selected language does not expose payload measurements")
    executions = 4 * sum(1 << n for n in range(1, args.max_inputs + 1))
    work = 4 * sum(
        (1 << n) * max(64 * (1 << n) + 64 * n + 512, 100 * n + 8192)
        for n in range(1, args.max_inputs + 1)
    )
    plan = {
        "case_ids": [
            case_id(language, n, family, table)
            for language in languages
            for n in range(1, args.max_inputs + 1)
            for family, table in corpus(n).items()
        ],
        "languages": len(languages),
        "tables": 4 * args.max_inputs * len(languages),
        "row_executions": executions * len(languages),
        "step_bound": work * len(languages),
    }
    if not supervise(parser, args, Path(__file__), plan):
        return
    for language in languages:
        for n in range(1, args.max_inputs + 1):
            for family, table in corpus(n).items():
                identifier = case_id(language, n, family, table)
                cached = reused(identifier)
                profile = (
                    cached["profile"]
                    if cached is not None
                    else audit(language, n, table)
                )
                completed(
                    "executed",
                    case_id=identifier,
                    reused=cached is not None,
                    rows=len(table),
                    family=family,
                    profile=profile,
                    **profile,
                )
                print(json.dumps({"family": family, **profile}))


if __name__ == "__main__":
    main()
