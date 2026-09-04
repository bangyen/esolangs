"""The text-generator-blockers table is pinned to the registry.

``docs/limitations.md`` carries a table naming every language that has no
text generator and why one cannot exist.  Nothing enforced it, and it
drifted: the registry listed seventeen such languages while the table had
fifteen rows, so Fargo and Inject were blocked for reasons recorded only in
their interpreter docstrings and nowhere a reader would look.

The pin runs in both directions, the way
``tests/compilers/test_assembly_compilers.py`` pins the compiler roster: a
language that loses its text generator fails here until somebody writes
down why, and a row left behind for a language that has since gained one
fails the other way.  A table nothing checks is how this repo has been
bitten before -- a hard-coded category tuple exempted twelve interpreters
and hid three real violations.
"""

import pathlib
import re

from esolangs.registry import LANGUAGES

_DOC = pathlib.Path(__file__).resolve().parents[1] / "docs" / "limitations.md"

_HEADING = "## Text generator blockers"


def _documented() -> set[str]:
    """Return the language names the blockers table has a row for.

    The table is the block of ``|``-delimited rows following the heading,
    ending at the first blank line after it.  The header and its ``---``
    separator are skipped by name rather than by position, so reordering
    the table cannot silently drop a row from the set.
    """
    text = _DOC.read_text(encoding="utf-8")
    start = text.index(_HEADING)
    body = text[start + len(_HEADING) :]
    names = set()
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if names:
                break
            continue
        if not stripped.startswith("|"):
            break
        cell = stripped.split("|")[1].strip()
        if cell in {"Language", ""} or re.fullmatch(r"-+", cell):
            continue
        names.add(cell)
    return names


def test_blockers_table_matches_the_registry() -> None:
    """Every text-generator-less language has a row, and no row is stale."""
    expected = {name for name, lang in LANGUAGES.items() if not lang.text}
    documented = _documented()

    missing = sorted(expected - documented)
    stale = sorted(documented - expected)

    assert not missing, (
        f"languages with no text generator and no documented reason: {missing}"
    )
    assert not stale, (
        f"blockers-table rows for languages that have a text generator: {stale}"
    )


def test_the_table_is_not_empty() -> None:
    """A parser that silently matched nothing would pass the pin vacuously.

    ``_documented`` returns a set built by scanning; if the heading text or
    the table format changed, it could return an empty set and the
    both-directions assert above would still pass whenever the registry
    happened to agree.  Pinning a floor makes that failure loud.
    """
    assert len(_documented()) >= 15
