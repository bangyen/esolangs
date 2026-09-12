r"""The shared body of the per-language ``run and capture its output``."""

import contextlib
from collections.abc import Callable
from typing import Any

from esolangs.interpreters.io import ScriptedIO

__all__ = ["run_program"]


def run_program(
    run: Callable[..., Any],
    code: Any,
    stdin: str = "",
    *,
    limit: int | None = None,
    suppress_eof: bool = True,
    **run_kwargs: Any,
) -> str:
    r"""Run ``code`` through ``run`` and return everything it printed."""
    io = ScriptedIO(stdin)
    kwargs = dict(run_kwargs) if limit is None else {"limit": limit, **run_kwargs}
    halts: tuple[type[BaseException], ...] = (EOFError,) if suppress_eof else ()
    with contextlib.suppress(*halts):
        run(code, io, **kwargs)
    return io.getvalue()
