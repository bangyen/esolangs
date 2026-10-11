"""Language-specific generator execution helpers."""

from collections.abc import Iterator

from tests.generators.boolean_runners import _run_from, _runner

run_polynomial = _runner("polynomial")


def run_polynomial_from(program: str, feed: Iterator[str]) -> str:
    """Run a Polynomial program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.languages.polynomial.interpreter", program, feed)
