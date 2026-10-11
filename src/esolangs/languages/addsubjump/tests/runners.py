"""Language-specific generator execution helpers."""

from collections.abc import Iterator

from tests.generators.boolean_runners import _run_from, _runner

run_addsubjump = _runner("addsubjump")


def run_addsubjump_from(program: str, feed: Iterator[str]) -> str:
    """Run an AddSubJump program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.languages.addsubjump.interpreter", program, feed)
