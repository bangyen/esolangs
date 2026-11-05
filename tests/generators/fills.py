"""Template filling for suites that build programs from a generated template."""

import esolangs


def fill(name: str):
    """``(template, bits) -> program`` for a parameterized language."""
    return lambda template, bits: esolangs.instantiate(name, template, bits).source


def _run_form(pair: tuple[str, str], n: int) -> str:
    """A bare template of ``n`` runs, one per input, as wide as its setter."""
    return "$" * len(pair[0]) * n
