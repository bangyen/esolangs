"""Contract tests every boolean generator must satisfy.

These are cross-cutting invariants rather than per-language behaviour: they
sweep every registered boolean generator instead of asserting against one.
"""

import contextlib
import importlib

import pytest

import esolangs.tools.boolean as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import BY_FUNCTION

# Tables that exercise the constant-table paths alongside a normal one.  The
# constants are the interesting cases: a generator that special-cases them can
# lose the input reads that the non-constant path emits.
_TABLES = ["00000000", "11111111", "01101001", "00000001", "11111110"]


def _input_reading_generators() -> list[tuple[str, object]]:
    """Every boolean generator whose language actually reads input."""
    found = []
    for name in sorted(boolean.__all__):
        fn = getattr(boolean, name, None)
        lang = BY_FUNCTION.get(name)
        if not callable(fn) or lang is None or lang.interpreter is None:
            continue
        try:
            run = importlib.import_module(
                f"esolangs.interpreters.{lang.interpreter}"
            ).run
        except Exception:  # pragma: no cover - interpreter lives outside the pkg
            continue
        found.append((name, (fn, lang, run)))
    return found


def _reads(entry: tuple, table: str) -> int:
    """Run the generated program and report how many inputs it consumed."""
    fn, lang, run = entry
    program = str(fn(table))
    io = ScriptedIO("0\n" * 8)
    # A program may halt through its own error path or call exit; either way the
    # read count up to that point is what matters here.
    with contextlib.suppress(Exception, SystemExit):
        run(
            program.splitlines() if lang.split else program,
            io=io,
            **dict(lang.kwargs),
        )
    return io.position()


@pytest.mark.parametrize(
    ("name", "entry"),
    _input_reading_generators(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_every_table_reads_the_same_number_of_inputs(name: str, entry: tuple) -> None:
    """A generator reads its ``n`` inputs whatever the truth table says.

    An input-capable language reads each of its ``n`` inputs exactly once per
    run, and that must not depend on the *contents* of the table.  A generator
    that special-cases a constant table by printing the answer outright skips
    the reads, which leaves the caller's bits unread on the input stream for
    whatever runs next, and drops the per-read prompts that a prompting
    language (3x) emits -- prompts ``scripts/verify_extra_generators.py``
    filters precisely because they are part of the observable output.

    Shortening the *body* for a constant table is fine and worth doing; the
    reads are the interface and have to stay.
    """
    counts = {table: _reads(entry, table) for table in _TABLES}
    baseline = counts["01101001"]
    if baseline == 0:
        pytest.skip(f"{name} does not read input in this harness")
    assert set(counts.values()) == {baseline}, (
        f"{name} reads a different number of inputs depending on the table: "
        f"{counts} -- a constant table must still consume all {baseline}"
    )
