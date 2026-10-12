"""Language-specific generator execution helpers."""

from collections.abc import Iterator

from tests.generators.boolean_runners import _run_from, _runner

run_sophie = _runner("sophie")


def run_sophie_from(program: str, feed: Iterator[str]) -> str:
    """Run a Sophie program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.languages.sophie.interpreter", program, feed)
