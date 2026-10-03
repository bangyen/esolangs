"""Measure one generated artifact's size, time, steps, and actual answers."""

from __future__ import annotations

import argparse
import json
import signal
import statistics
import threading
import time
from typing import Any, cast

import esolangs
import esolangs.debugger as debugger_api
from esolangs._validate import check_timeout
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import VM, run_until_halt_or_cycle


def _bits(row: int, inputs: int) -> list[int]:
    return [(row >> shift) & 1 for shift in range(inputs - 1, -1, -1)]


def _source_size(program: esolangs.Program) -> int:
    if isinstance(program, str):
        return len(program)
    return sum(len(row) for row in program.rows)


def _integer_bits(value: int) -> int:
    """Count magnitude bits (one for zero) and a sign bit for negatives."""
    return max(1, value.bit_length()) + int(value < 0)


def _payload_profile(language: str, vm: VM) -> dict[str, int] | None:
    """Count logical data and control integers for three audited machine shapes.

    Excludes Python overhead, static parser indexes and I/O buffers. Subleq's
    mutable code is included in its memory; other source is measured separately.
    """
    state = vm.snapshot()
    if language == "BFStack":
        data, control, pc, _cursor = cast(
            "tuple[tuple[int, ...], tuple[int, ...], int, int]", state
        )
    elif language == "Sophie":
        pc, accumulator, _skip, control, _halted = cast(
            "tuple[int, int, bool, tuple[int, ...], bool]", state
        )
        data = (accumulator,)
    elif language == "Subleq":
        data, pc, _cursor = cast("tuple[tuple[int, ...], int, int]", state)
        control = ()
    else:
        return None
    widths = [_integer_bits(value) for value in (*data, *control)]
    return {
        "peak_control_stack_items": len(control),
        "peak_data_bits": sum(_integer_bits(value) for value in data),
        "peak_control_stack_bits": sum(_integer_bits(value) for value in control),
        "peak_integer_bits": max(widths, default=0),
        "peak_pc_bits": _integer_bits(pc),
    }


def _execute(
    language: str,
    program: esolangs.Program,
    table: str,
    row: int,
    cap: int,
    timeout: float | None,
    *,
    track_store: bool = False,
) -> dict[str, Any]:
    facts = esolangs.describe(language)
    bits = _bits(row, len(table).bit_length() - 1)
    source: esolangs.Program
    if facts["parameterized"]:
        assert isinstance(program, str)
        source, stdin = esolangs.instantiate(language, program, bits), ""
    else:
        source, stdin = program, esolangs.encode_inputs(language, bits, table)
    supported = facts["steppable_to_answer"]
    if track_store and facts["answer_mode"] == "termination":
        raise ValueError("store tracking requires a halting-answer language")
    result: dict[str, Any] = {
        "row": row,
        "expected_answer": table[row],
        "actual_answer": None,
        "matches": None,
        "commands": None,
        "stepping_status": "supported" if supported else "unsupported",
        "execution_status": "pending",
        "peak_memory_cells": None,
        "peak_stack_items": None,
        "peak_control_stack_items": None,
        "peak_data_bits": None,
        "peak_control_stack_bits": None,
        "peak_integer_bits": None,
        "peak_pc_bits": None,
    }

    def drive(*_args: object) -> None:
        if not supported:
            output = esolangs.run(language, source, stdin)
            result["execution_status"] = "halted"
            result["actual_answer"] = esolangs.read_answer(language, output)
            return
        vm = debugger_api.make_vm(language, source, stdin)
        terminating = facts["answer_mode"] == "termination"
        if terminating:
            halted = run_until_halt_or_cycle(vm, limit=cap)
            if not halted:
                result["execution_status"] = "cycle"
                result["actual_answer"] = str(
                    list(facts["answer_encoding"]).index("diverges")
                )
                return
            # The detector unwraps the VM; replay a halt to retain the
            # baseline's wrapper-step count, excluding its post-halt dump.
            vm = debugger_api.make_vm(language, source, stdin)

        def sample_store() -> None:
            if track_store:
                result["peak_memory_cells"] = max(
                    result["peak_memory_cells"] or 0, len(vm.memory)
                )
                result["peak_stack_items"] = max(
                    result["peak_stack_items"] or 0, len(vm.stack)
                )
                profile = _payload_profile(str(facts["name"]), vm)
                if profile is not None:
                    for key, value in profile.items():
                        result[key] = max(result[key] or 0, value)

        sample_store()
        steps = 0
        while not vm.halted and steps < cap:
            vm.step()
            steps += 1
            sample_store()
        result["commands"] = steps if vm.halted else None
        if not vm.halted:
            result["execution_status"] = "step_cap"
        elif terminating:
            result["execution_status"] = "halted"
            result["actual_answer"] = str(list(facts["answer_encoding"]).index("halts"))
        else:
            if facts["dumps_on_the_post_halt_step"]:
                vm.step()
            result["execution_status"] = "halted"
            result["actual_answer"] = esolangs.read_answer(language, vm.output)

    try:
        # Cover VM construction too: a step cap cannot bound factoring.
        esolangs._run(drive, source, ScriptedIO(stdin), timeout)  # noqa: SLF001
    except esolangs.ExecutionTimeoutError:
        result["execution_status"] = "timeout"
    except TimeoutError:
        result["execution_status"] = "step_cap"
    if result["actual_answer"] is not None:
        result["matches"] = result["actual_answer"] == result["expected_answer"]
    return result


def _commands(
    language: str,
    program: esolangs.Program,
    table: str,
    row: int,
    cap: int,
) -> int | None:
    """Return steps to halt for the size screens, checking the same artifact."""
    result = _execute(language, program, table, row, cap, None)
    if result["matches"] is False:
        raise ValueError(f"{language} row {row}: wrong generated answer")
    return cast("int | None", result["commands"])


def measure(
    language: str,
    table: str,
    *,
    repeat: int,
    row: int,
    step_cap: int,
    all_rows: bool = False,
    sample_rows: tuple[int, ...] | None = None,
    timeout: float | None = 30.0,
    track_store: bool = False,
) -> dict[str, Any]:
    """Benchmark the last timed artifact; optionally check every input row."""
    if repeat < 1 or step_cap < 1:
        raise ValueError("repeat and step_cap must be positive")
    if not 0 <= row < len(table):
        raise ValueError("row must index the truth table")
    if sample_rows is not None and (
        not sample_rows
        or row not in sample_rows
        or any(not 0 <= at < len(table) for at in sample_rows)
    ):
        raise ValueError("sample rows must index the table and include row")
    check_timeout(timeout)
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        raise esolangs.ArgumentError(
            "benchmark timeout needs a Unix main thread; pass timeout=None"
        )
    timings: list[int] = []
    program: esolangs.Program | None = None
    for _ in range(repeat):
        started = time.perf_counter_ns()
        program = esolangs.generate(language, table)
        _source_size(program)
        timings.append(time.perf_counter_ns() - started)
    assert program is not None
    rows = range(len(table)) if all_rows else sample_rows or (row,)
    executions = [
        _execute(
            language, program, table, at, step_cap, timeout, track_store=track_store
        )
        for at in rows
    ]
    selected = next(item for item in executions if item["row"] == row)
    return {
        "schema": 4,
        "track_store": track_store,
        "language": esolangs.describe(language)["name"],
        "truth_table": table,
        "inputs": len(table).bit_length() - 1,
        "source_kind": esolangs.describe(language)["source_kind"],
        "source_units": _source_size(program),
        "generation_ns_best": min(timings),
        "generation_ns_median": int(statistics.median(timings)),
        "step_cap": step_cap,
        "timeout": timeout,
        "all_rows": all_rows,
        "executions": executions,
        "worst_row_commands": (
            max(item["commands"] for item in executions)
            if all_rows and all(item["commands"] is not None for item in executions)
            else None
        ),
        **selected,
    }


def main(argv: list[str] | None = None) -> int:
    """Print JSON evidence; fail if any requested row is wrong or undecided."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("language")
    parser.add_argument("truth_table")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--row", type=int)
    parser.add_argument("--step-cap", type=int, default=2_000_000)
    bounds = parser.add_mutually_exclusive_group()
    bounds.add_argument("--timeout", type=float, default=30.0)
    bounds.add_argument(
        "--no-timeout", action="store_const", dest="timeout", const=None
    )
    parser.add_argument("--all-rows", action="store_true")
    parser.add_argument(
        "--track-store",
        action="store_true",
        help="sample stores; Sophie/BFStack/Subleq also report integer payloads",
    )
    args = parser.parse_args(argv)
    if args.repeat < 1 or args.step_cap < 1:
        parser.error("--repeat and --step-cap must be positive")
    row = len(args.truth_table) - 1 if args.row is None else args.row
    if not 0 <= row < len(args.truth_table):
        parser.error(f"--row must be in [0, {len(args.truth_table) - 1}]")
    result = measure(
        args.language,
        args.truth_table,
        repeat=args.repeat,
        row=row,
        step_cap=args.step_cap,
        all_rows=args.all_rows,
        timeout=args.timeout,
        track_store=args.track_store,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all(item["matches"] is True for item in result["executions"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
