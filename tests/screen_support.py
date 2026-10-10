"""Table corpora and per-row audits the generator tests use.

Moved out of ``scripts/screens`` when the measurement screens were removed.
The corpora are pinned by seed, so a size or a bound a test records against
one of them stays reproducible.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

import esolangs
from esolangs._evaluate import _terminates
from scripts import benchmark

#: Step cap for a candidate row, matching the removed screen's.
CAP = 10**7


def random_table(n: int, rng: random.Random) -> str:
    """Return a uniformly random ``n``-input table."""
    return format(rng.getrandbits(1 << n), f"0{1 << n}b")


def tiled(n: int, rng: random.Random) -> str:
    """Return an ``n``-input table tiled from two random smaller tables.

    Its subtrees repeat, which a random table's almost never do.
    """
    k = rng.randint(1, n - 2)
    blocks = [random_table(k, rng), random_table(k, rng)]
    return "".join(rng.choice(blocks) for _ in range(1 << (n - k)))


def ignore(table: str, at: int) -> str:
    """Return ``table`` with a new input at position ``at`` it never reads."""
    low = len(table).bit_length() - 1 - at  # inputs after the new one
    mask = (1 << low) - 1
    return "".join(
        table[(row >> (low + 1) << low) | (row & mask)] for row in range(2 * len(table))
    )


def corpus(n: int) -> dict[str, str]:
    """Return constants, dense, constant-half, tiled and ignored-input tables."""
    rng = random.Random(2026 + n)
    dense = random_table(n, rng)
    found = {"zero": "0" * (1 << n), "one": "1" * (1 << n), "dense": dense}
    if n > 1:
        inner = random_table(n - 1, rng)
        found["constant-half"] = inner + "0" * len(inner)
        for at in sorted({0, n // 2, n - 1}):
            found[f"ignored-{at}"] = ignore(inner, at)
    if n > 2:
        found["tiled"] = tiled(n, rng)
    return found


def resource_corpus(n: int) -> dict[str, str]:
    """Return four reproducible tables without searching."""
    width = 1 << n
    rng = random.Random(n)
    return {
        "zero": "0" * width,
        "one": "1" * width,
        "parity": "".join(str(row.bit_count() % 2) for row in range(width)),
        "dense": f"{rng.getrandbits(width):0{width}b}",
    }


def execute(
    name: str,
    program: esolangs.Program,
    table: str,
    options: dict[str, Any],
    *,
    all_rows: bool,
) -> int:
    """Check bounded actual answers, including cycle-proved termination answers."""
    n = len(table).bit_length() - 1
    facts = esolangs.describe(name)
    settings = options.get("settings")
    rows = (
        range(len(table)) if all_rows else sorted({0, len(table) // 2, len(table) - 1})
    )
    source: esolangs.Program
    for row in rows:
        bits = [int(bit) for bit in format(row, f"0{n}b")]
        if facts["parameterized"]:
            source = esolangs.instantiate(name, program, bits, settings=settings)
            stdin = ""
        else:
            source = program
            stdin = esolangs.encode_inputs(name, bits, truth_table=table)
        if facts["answer_mode"] == "termination":
            assert isinstance(source, str)
            encoding = facts["answer_encoding"]
            actual = _terminates(
                name,
                source,
                stdin,
                2,
                str(encoding.index("halts")),
                str(encoding.index("diverges")),
                settings=settings,
            )
        else:
            actual = esolangs.read_answer(
                name,
                esolangs.run(name, source, stdin=stdin, timeout=2, settings=settings),
            )
        if actual != table[row]:
            raise ValueError(f"{name} row {row}: {actual!r} != {table[row]!r}")
    return len(rows)


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
    result = benchmark.measure(
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


def _worst(
    language: str,
    program: esolangs.Program,
    table: str,
    rows: list[int],
    timeout: float = 30.0,
) -> tuple[int, int]:
    """Return ``(wrong rows, worst steps)``; an unanswered row is wrong."""
    wrong = worst = 0
    for row in rows:
        result = benchmark._execute(  # noqa: SLF001
            language, program, table, row, CAP, timeout
        )
        wrong += result["matches"] is not True
        worst = max(worst, result["commands"] or 0)
    return wrong, worst
