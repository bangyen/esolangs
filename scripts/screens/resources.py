"""Execute every row of bounded constant, parity and seeded dense tables."""

import argparse
import json
import random
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
        timeout=None,
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
    args = parser.parse_args()
    if not 1 <= args.max_inputs <= 10:
        parser.error("--max-inputs must be between 1 and 10")
    from esolangs.registry import LANGUAGES

    for language in [name for name, lang in LANGUAGES.items() if lang.payload]:
        for n in range(1, args.max_inputs + 1):
            for family, table in corpus(n).items():
                print(json.dumps({"family": family, **audit(language, n, table)}))


if __name__ == "__main__":
    main()
