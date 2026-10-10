"""Supervise reusable benchmark workers with portable phase deadlines."""

from __future__ import annotations

import builtins
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import esolangs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _verify_process import EXCERPT_BYTES, stop_process_tree

MAX_RECORD_CHARS = 1024 * 1024


class Worker:
    """Reuse one interpreter across a sweep; kill the tree on any deadline."""

    def __init__(self, command: list[str] | None = None) -> None:
        self.command = command or [
            sys.executable,
            str(Path(__file__).with_name("_benchmark_worker.py")),
        ]
        self.process: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[str | None] = queue.Queue(maxsize=1)
        self.stopped = threading.Event()
        self.reader: threading.Thread | None = None
        self.writer: threading.Thread | None = None
        self.log_path: Path | None = None

    def start(self) -> subprocess.Popen[str]:
        if self.process is None:
            self.messages = queue.Queue(maxsize=1)
            self.stopped = threading.Event()
            directory = Path(__file__).resolve().parents[1] / "notes" / "benchmarks"
            directory.mkdir(parents=True, exist_ok=True)
            fd, filename = tempfile.mkstemp(
                prefix="worker-", suffix=".log", dir=directory
            )
            self.log_path = Path(filename)
            try:
                self.process = subprocess.Popen(
                    self.command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=fd,
                    text=True,
                    encoding="utf-8",
                    start_new_session=os.name == "posix",
                    cwd=Path(__file__).resolve().parents[1],
                )
            finally:
                os.close(fd)
            process = self.process
            messages, stopped = self.messages, self.stopped

            def read() -> None:
                assert process.stdout is not None
                while not stopped.is_set():
                    line = process.stdout.readline(MAX_RECORD_CHARS + 1) or None
                    oversized = line is not None and len(line) > MAX_RECORD_CHARS
                    if oversized:
                        line = json.dumps(
                            {
                                "error": {
                                    "type": "RuntimeError",
                                    "message": "benchmark worker record exceeds limit",
                                }
                            }
                        )
                    while not stopped.is_set():
                        try:
                            messages.put(line, timeout=0.05)
                            break
                        except queue.Full:
                            pass
                    if line is None or oversized:
                        break

            self.reader = threading.Thread(target=read, daemon=True)
            self.reader.start()
        return self.process

    def close(self) -> None:
        if self.process is not None:
            self.stopped.set()
            stop_process_tree(self.process)
            if self.reader is not None:
                self.reader.join(5)
            if self.writer is not None:
                self.writer.join(5)
            for stream in (self.process.stdin, self.process.stdout):
                if stream is not None:
                    stream.close()
            self.process = None

    def measure(
        self,
        arguments: dict[str, Any],
        identity: dict[str, Any],
        generation_timeout: float | None,
    ) -> dict[str, Any]:
        process = self.start()
        phase, limit = "generation", generation_timeout
        deadline = None if limit is None else time.monotonic() + limit
        generated = False
        executed = 0
        expected = (
            len(arguments.get("table", ""))
            if arguments.get("all_rows")
            else len(arguments.get("sample_rows") or (0,))
        )
        try:
            messages, stopped = self.messages, self.stopped

            def send() -> None:
                assert process.stdin is not None
                try:
                    process.stdin.write(
                        json.dumps({"arguments": arguments, "identity": identity})
                        + "\n"
                    )
                    process.stdin.flush()
                except OSError as error:
                    failure = json.dumps(
                        {"error": {"type": type(error).__name__, "message": str(error)}}
                    )
                    while not stopped.is_set():
                        try:
                            messages.put(failure, timeout=0.05)
                            break
                        except queue.Full:
                            pass

            self.writer = threading.Thread(target=send, daemon=True)
            self.writer.start()
            while True:
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.monotonic())
                )
                try:
                    line = self.messages.get(timeout=remaining)
                except queue.Empty:
                    raise esolangs.ExecutionTimeoutError(
                        f"benchmark {phase} deadline exceeded ({limit:g}s)"
                    ) from None
                if line is None:
                    raise RuntimeError("benchmark worker exited without evidence")
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise RuntimeError("invalid benchmark worker record")
                if "phase" in message:
                    next_phase = message["phase"]
                    if (
                        next_phase == "generation"
                        and not generated
                        and set(message) == {"phase"}
                    ):
                        generated = True
                    elif (
                        next_phase == "execution"
                        and generated
                        and executed < expected
                        and type(message.get("index")) is int
                        and message["index"] == executed
                        and set(message) == {"phase", "index"}
                    ):
                        phase = next_phase
                        executed += 1
                        limit = arguments["timeout"]
                        deadline = None if limit is None else time.monotonic() + limit
                    else:
                        raise RuntimeError("invalid benchmark worker phase transition")
                elif "result" in message:
                    if (
                        not generated
                        or executed != expected
                        or set(message) != {"result"}
                        or not isinstance(message["result"], dict)
                    ):
                        raise RuntimeError(
                            "premature or invalid benchmark worker result"
                        )
                    return dict(message["result"])
                elif "error" in message:
                    error = message["error"]
                    if (
                        set(message) != {"error"}
                        or not isinstance(error, dict)
                        or set(error) != {"type", "message"}
                        or not all(isinstance(value, str) for value in error.values())
                    ):
                        raise RuntimeError("invalid benchmark worker error")
                    cls = getattr(
                        esolangs,
                        error["type"],
                        getattr(builtins, error["type"], RuntimeError),
                    )
                    if not isinstance(cls, type) or not issubclass(cls, Exception):
                        cls = RuntimeError
                    raise cls(error["message"])
                else:
                    raise RuntimeError("invalid benchmark worker record")
        except BaseException as error:
            self.close()
            if isinstance(error, Exception) and self.log_path is not None:
                with self.log_path.open("rb") as log:
                    log.seek(max(0, self.log_path.stat().st_size - EXCERPT_BYTES))
                    tail = log.read(EXCERPT_BYTES).decode("utf-8", errors="replace")
                error.add_note(f"[log] {self.log_path}\n{tail}")
            raise
