"""CLI options and an absolute wall-clock budget for a benchmark request."""

from __future__ import annotations

import argparse
import queue
import time
from typing import TYPE_CHECKING

from esolangs.exceptions import ExecutionTimeoutError
from esolangs.runtime._validate import check_timeout

if TYPE_CHECKING:
    from threading import Event

DEFAULT_TOTAL_TIMEOUT = 300.0


class BenchmarkDeadline:
    """Keep the same deadline across input, generation and all execution rows."""

    def __init__(self, seconds: float = DEFAULT_TOTAL_TIMEOUT) -> None:
        """Start the deadline with a positive, finite duration."""
        duration = check_timeout(seconds, "--total-timeout")
        assert duration is not None
        self.seconds = duration
        self.expires = time.monotonic() + duration

    def remaining(self) -> float:
        """Return the remaining budget or raise before doing more work."""
        remaining = self.expires - time.monotonic()
        if remaining <= 0:
            raise self.expired()
        return remaining

    def expired(self) -> ExecutionTimeoutError:
        """Report the exhausted request budget."""
        return ExecutionTimeoutError(
            f"benchmark total deadline exceeded ({self.seconds:g}s)"
        )

    def wait_for_record(
        self,
        messages: queue.Queue[str | None],
        phase: str,
        limit: float | None,
        phase_deadline: float | None,
    ) -> str | None:
        """Wait for a worker record without renewing the request budget."""
        remaining = self.remaining()
        phase_remaining = (
            None
            if phase_deadline is None
            else max(0.0, phase_deadline - time.monotonic())
        )
        total_limited = phase_remaining is None or remaining <= phase_remaining
        try:
            record = messages.get(
                timeout=remaining if total_limited else phase_remaining
            )
        except queue.Empty:
            if total_limited:
                raise self.expired() from None
            raise ExecutionTimeoutError(
                f"benchmark {phase} deadline exceeded ({limit:g}s)"
            ) from None
        self.remaining()
        return record


def post_record(
    messages: queue.Queue[str | None], stopped: Event, record: str | None
) -> None:
    """Queue a record until this worker stops.

    A restart rebinds the queue and event so the old thread cannot post to
    the new worker's queue.
    """
    while not stopped.is_set():
        try:
            messages.put(record, timeout=0.05)
            return
        except queue.Full:
            pass


def check_piped_rows(
    parser: argparse.ArgumentParser,
    rows: list[int] | None,
    language: str,
    cap: int | None,
) -> None:
    """Refuse row indices beyond the generator's maximum before reading stdin."""
    max_row = max(rows or (0,))
    if cap is not None and max_row.bit_length() > cap:
        parser.error(
            f"--row {max_row} exceeds {language}'s generator limit (max-inputs={cap})"
        )


def argument_parser(description: str) -> argparse.ArgumentParser:
    """Build the benchmark CLI parser."""
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("language")
    parser.add_argument(
        "truth_table",
        help="one output bit per input row: 0110 is two-input XOR; '-' reads stdin",
    )
    parser.add_argument("--repeat", type=int, default=3)
    rows = parser.add_mutually_exclusive_group()
    rows.add_argument("--row", type=int, action="append", help="input row (repeatable)")
    rows.add_argument("--all-rows", action="store_true", help="run every input row")
    parser.add_argument("--step-cap", type=int, default=2_000_000)
    bounds = parser.add_mutually_exclusive_group()
    bounds.add_argument("--timeout", type=float, default=30.0, help="seconds per row")
    bounds.add_argument(
        "--no-timeout",
        action="store_const",
        dest="timeout",
        const=None,
        help="disable the per-row deadline",
    )
    parser.add_argument("--generation-timeout", type=float, default=30.0)
    parser.add_argument(
        "--total-timeout",
        type=float,
        default=DEFAULT_TOTAL_TIMEOUT,
        help=f"seconds for the whole request (default: {DEFAULT_TOTAL_TIMEOUT:g})",
    )
    layout = parser.add_mutually_exclusive_group()
    layout.add_argument("--width", type=int, help="request a column width")
    layout.add_argument("--balance", action="store_true", help="balance the layout")
    parser.add_argument("--scale", type=int, help="replicate raster pixels")
    parser.add_argument(
        "-s", "--settings", action="append", help="dialect overrides as JSON"
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        help="repeatable dialect KEY=VALUE override",
    )
    parser.add_argument(
        "--track-store",
        action="store_true",
        help="sample stores; languages with a payload split report integers too",
    )
    return parser
