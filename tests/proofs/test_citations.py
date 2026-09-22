"""The papers' numbered cross-references resolve to the results they name.

``polynomial.tex`` imports its coefficient-mass bound from the companion
manuscript by number -- ``\\cite[Corollary~3.4]{coefficient-mass}`` -- and the
Markdown companion and the ledger cite it and the confluent analogue the same
way.  A number is not a link: reordering or inserting a result in
``coefficient-mass.tex`` renumbers everything after it and leaves every
citation pointing at the wrong statement, silently and while still compiling.

So recompute the numbering from the source the way LaTeX does -- one counter
shared by the four theorem environments, reset per ``\\section`` -- and hold
each citation to the label it is supposed to name.  The expectations are
labels, not numbers, because the label is what the citing sentence means.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

#: Resolved from this file, not the working directory, for the same reason
#: :mod:`tests.proofs._ledger` does it: `just`, the repo root and a worktree
#: are all valid places to run from.
PROOFS = Path(__file__).resolve().parents[2] / "docs" / "proofs"

#: The environments sharing one counter, from the ``\newtheorem`` block at the
#: head of ``coefficient-mass.tex``, mapped to the word a citation spells.
ENVIRONMENTS = {
    "theorem": "Theorem",
    "lemma": "Lemma",
    "corollary": "Corollary",
    "proposition": "Proposition",
}

#: Every numbered cross-reference into the companion, as
#: ``(citing file, cited number) -> (word, label)``.  The test also checks
#: that this table is complete, so a new citation fails here until listed.
CITATIONS = {
    ("index.md", "3.4"): ("Corollary", "cor:mass"),
    ("polynomial.md", "3.8"): ("Proposition", "prop:confluent"),
    ("polynomial.tex", "3.4"): ("Corollary", "cor:mass"),
}

#: A numbered reference in running text or in a ``\cite`` option.
_REFERENCE = re.compile(
    r"(Theorem|Lemma|Corollary|Proposition)[~ ]+(\d+\.\d+)",
)

#: ``\begin{corollary}[Title]`` and the ``\label`` that follows it, which may
#: sit on the next line (``prop:subtwo`` does).
_BEGIN = re.compile(r"\\begin\{(" + "|".join(ENVIRONMENTS) + r")\}(?:\[([^]]*)\])?")
_LABEL = re.compile(r"\\label\{([^}]*)\}")
_SECTION = re.compile(r"^\\section\{")


def _numbering() -> dict[str, tuple[str, str, str]]:
    """Map each ``coefficient-mass.tex`` result number to its result.

    The value is ``(word, label, title)``; the numbering is LaTeX's, one
    counter shared across the four environments and reset by ``\\section``.
    """
    lines = (PROOFS / "coefficient-mass.tex").read_text().splitlines()
    numbered: dict[str, tuple[str, str, str]] = {}
    section = 0
    counter = 0
    for index, line in enumerate(lines):
        if _SECTION.match(line):
            section += 1
            counter = 0
            continue
        begin = _BEGIN.search(line)
        if begin is None:
            continue
        counter += 1
        # The label is on the ``\begin`` line or the one after it; nothing in
        # the paper puts anything else between the two.
        label = _LABEL.search(line) or _LABEL.search(lines[index + 1])
        assert label is not None, f"unlabelled result at line {index + 1}"
        numbered[f"{section}.{counter}"] = (
            ENVIRONMENTS[begin.group(1)],
            label.group(1),
            begin.group(2) or "",
        )
    return numbered


def _cited(name: str) -> set[tuple[str, str]]:
    """The ``(word, number)`` references to the companion made by ``name``.

    A reference counts when its own ``\\cite`` names the companion, or -- in
    Markdown, which has no ``\\cite`` -- when its line does.  That skips the
    two ``Theorem~4.1`` citations of Karlin and Studden, which name a
    different key.
    """
    found: set[tuple[str, str]] = set()
    for line in (PROOFS / name).read_text().splitlines():
        for match in _REFERENCE.finditer(line):
            cite = re.search(r"\\cite\[[^]]*\]\{([^}]*)\}", line)
            key = cite.group(1) if cite else ""
            if "coefficient-mass" in (key or line):
                found.add((match.group(1), match.group(2)))
    return found


@pytest.mark.parametrize(("citation", "expected"), sorted(CITATIONS.items()))
def test_citation_resolves(
    citation: tuple[str, str], expected: tuple[str, str]
) -> None:
    """Each cited number is the labelled result the citing paper means."""
    _, number = citation
    word, label, _ = _numbering()[number]
    assert (word, label) == expected


def test_every_citation_is_covered() -> None:
    """No file cites the companion by a number this table does not list."""
    for name in ("index.md", "polynomial.md", "polynomial.tex"):
        listed = {
            (word, number)
            for (file, number), (word, _) in CITATIONS.items()
            if file == name
        }
        assert _cited(name) == listed, name


def test_the_cited_titles_are_the_ones_the_papers_name() -> None:
    """The bibliography entry's parenthetical names Corollary 3.4's title."""
    numbering = _numbering()
    assert numbering["3.4"][2] == "Logarithmic mass"
    assert numbering["3.8"][2] == "Confluent analogue"
    bibliography = (PROOFS / "polynomial.tex").read_text()
    assert "Corollary~3.4\n(Logarithmic mass)" in bibliography
