"""The shared body of the per-language ``run and capture its output`` helper.

Nearly every interpreter test file opens with the same four lines: build an
IO, call the language's ``run``, return what it wrote.  What differed between
the copies was not the language but the *idiom* -- about twenty files patched
``builtins.input`` and captured with ``redirect_stdout``, while the rest used
:class:`ScriptedIO` and its ``getvalue``.

The two are not equivalent at the edge.  A patched ``input`` whose
``side_effect`` list runs out raises ``StopIteration``, which is a mock
artifact no interpreter has a reason to handle; ``ScriptedIO`` raises
``EOFError``, which is what a real end of input looks like and what the
forty-nine interpreters that catch it are written against.  Standardizing on
``ScriptedIO`` is therefore a correctness point and not only a tidiness one,
even though no test in the suite currently exhausts a patched list.

:func:`run_program` is :mod:`tests.interpreters.oisc`'s helper with its two
OISC-specific assumptions lifted: the ``limit`` is optional rather than
always passed, and suppressing ``EOFError`` is a per-call choice rather than
unconditional.  Both had to become parameters for the same reason -- the
languages disagree.  Grapheme reads until the input runs out and treats the
``EOFError`` as its halt, while Decleq's own tests assert the ``EOFError``
escapes, so neither answer can be the only one.

Files whose helper takes something other than a program and a stdin -- A
Painter Ant's ``cycles``, Wumpus's ``heading``, the ones whose first
argument is a target string or a number -- keep their own, since what
varies there is the language's interface rather than the idiom.
"""

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
) -> str:
    """Run ``code`` through ``run`` and return everything it printed.

    ``run`` is the interpreter's own entry point, taken as an argument so
    one body serves every language.  ``code`` is whatever that ``run``
    accepts -- a source string for most, a list of lines for the grid
    languages -- and is passed straight through.

    ``limit`` is forwarded only when given, since most ``run`` signatures
    have no such parameter and would reject it.  ``suppress_eof`` swallows
    the ``EOFError`` of a program that reads past its input, which is the
    normal halt for the languages that read until exhaustion; the tests
    that assert the error escapes pass ``False``.
    """
    io = ScriptedIO(stdin)
    kwargs = {} if limit is None else {"limit": limit}
    if suppress_eof:
        with contextlib.suppress(EOFError):
            run(code, io, **kwargs)
    else:
        run(code, io, **kwargs)
    return io.getvalue()
