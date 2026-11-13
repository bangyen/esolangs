"""The shared body of the per-language ``run and capture its output`` helper."""

import contextlib
import io
from collections.abc import Callable
from typing import Any

from esolangs.runtime.io import IO, ScriptedIO

__all__ = ["native_runner", "run_lines", "run_printing", "run_program"]


def run_program(
    run: Callable[..., Any],
    code: Any,
    stdin: str = "",
    *,
    limit: int | None = None,
    suppress_eof: bool = True,
    **run_kwargs: Any,
) -> str:
    """Run ``code`` through ``run`` and return everything it printed.

    Exhausted input ends the run quietly; ``suppress_eof=False`` (or
    :func:`native_runner`) lets a test assert the ``EOFError``.
    """
    io = ScriptedIO(stdin)
    kwargs = dict(run_kwargs) if limit is None else {"limit": limit, **run_kwargs}
    halts: tuple[type[BaseException], ...] = (EOFError,) if suppress_eof else ()
    with contextlib.suppress(*halts):
        run(code, io, **kwargs)
    return io.getvalue()


def native_runner(run: Callable[..., Any]) -> Callable[..., str]:
    """Bind a native runner without swallowing EOF."""
    return lambda code, stdin="": run_program(run, code, stdin, suppress_eof=False)


def run_printing(run: Callable[..., Any], code: Any) -> str:
    """Run ``code`` with an ``IO`` that prints; return what reached stdout."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


def run_lines(run: Callable[..., Any]) -> Callable[..., str]:
    """``(code, inputs=None) -> output``, feeding each input as one line."""

    def run_and_capture(code: Any, inputs: list[str] | None = None) -> str:
        return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))

    return run_and_capture
