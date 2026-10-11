"""Language-specific generator execution helpers."""

from collections.abc import Iterator

from tests.generators.boolean_runners import _run_from, _runner

run_six_five = _runner("six_five")


def run_six_five_from(program: str, feed: Iterator[str]) -> str:
    """Run a 6-5 program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.languages.six_five.interpreter", program, feed)
