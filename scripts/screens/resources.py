"""Execute every row of bounded constant, parity and seeded dense tables."""

import argparse
import json
import random
import sys
from pathlib import Path

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


def audit(language: str, n: int, table: str) -> dict[str, int | str]:
    """Check answers and construction bounds; report exposed VM store lengths."""
    result = measure(
        language,
        table,
        repeat=1,
        row=0,
        step_cap=64 * len(table) + 64 * n + 512
        if language == "Subleq"
        else 100 * n + 8192,
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
        )
    }
    if language == "Sophie":
        # No loop opcode: each executed command advances the source cursor.
        assert commands <= result["source_units"]
        assert memory == 1
        assert stack == 0
        assert payload["peak_control_stack_items"] == 0
    elif language == "BFStack":
        # Prefix arms cost <100 each. The <=7-bit leaf normalizes <=7
        # bytes, adds <=127 weights and visits <=128 cascade guards;
        # even charging 256 iterations for every final byte loop fits 8192.
        assert commands <= 100 * n + 8192
        assert memory == 0
        assert stack <= 2 * max(n - 7, 0) + 3
        # Each seven-bit cascade nests one loop per listed row, plus its
        # outer loop and payload; each prefix branch adds one live loop.
        assert payload["peak_control_stack_items"] <= max(n - 7, 0) + 2 ** min(n, 7) + 2
        assert payload["peak_integer_bits"] <= max(
            8, result["source_units"].bit_length()
        )
    elif language == "Subleq":
        # Eight instructions per input, fewer than 60 fixed instructions and
        # 18 registers, then ceil(T/n) chunks. Selection costs <16T commands;
        # repeated unary division costs <32T, with <64n+512 setup commands.
        cell_bound = 24 * n + 200 + (len(table) + n - 1) // n
        assert commands <= 64 * len(table) + 64 * n + 512
        assert memory <= cell_bound
        assert stack == payload["peak_control_stack_items"] == 0
        assert payload["peak_integer_bits"] <= max(
            n + 1, cell_bound.bit_length() + 1, 7
        )
    else:
        raise ValueError("resource bounds cover Sophie, BFStack and Subleq")
    return {
        "language": language,
        "inputs": n,
        "source_units": result["source_units"],
        "worst_row_commands": commands,
        "peak_memory_cells": memory,
        "peak_stack_items": stack,
        **payload,
    }


def main() -> None:
    """Print checked resource profiles through a bounded arity."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-inputs", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.max_inputs <= 10:
        parser.error("--max-inputs must be between 1 and 10")
    for language in ("Sophie", "BFStack", "Subleq"):
        for n in range(1, args.max_inputs + 1):
            for family, table in corpus(n).items():
                print(json.dumps({"family": family, **audit(language, n, table)}))


if __name__ == "__main__":
    main()
