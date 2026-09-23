"""The papers' numbered cross-references resolve to the results they name.

``polynomial.tex`` imports its coefficient-mass bound from the companion
manuscript by number -- ``\\cite[Corollary~3.4]{coefficient-mass}`` -- and the
Markdown companion and the ledger cite it and the confluent analogue the same
way.  A number is not a link: reordering or inserting a result renumbers
everything after it, and splitting a paper in two renumbers from the start,
leaving a citation pointing at the wrong statement -- or at no statement --
silently and while still compiling.

So recompute each cited paper's numbering from its own source the way LaTeX
does -- one counter shared by the four theorem environments, reset per
``\\section`` -- and hold each citation to the paper and the label it is
supposed to name.  The expectations are labels, not numbers, because the label
is what the citing sentence means.
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
#: head of each cited paper, mapped to the word a citation spells.
ENVIRONMENTS = {
    "theorem": "Theorem",
    "lemma": "Lemma",
    "corollary": "Corollary",
    "proposition": "Proposition",
}

#: Every numbered cross-reference into a companion paper, as
#: ``(citing file, cited paper, number) -> (word, label)``.  The test also
#: checks that this table is complete, so a new citation fails here until it
#: is listed.
CITATIONS = {
    ("coefficient-mass-attainment.tex", "coefficient-mass", "4.1"): (
        "Proposition",
        "prop:sharp23",
    ),
    ("index.md", "coefficient-mass", "3.4"): ("Corollary", "cor:mass"),
    ("polynomial.md", "coefficient-mass-attainment", "2.1"): (
        "Proposition",
        "prop:confluent",
    ),
    ("polynomial.tex", "coefficient-mass", "3.4"): ("Corollary", "cor:mass"),
}

#: The files whose citations the table above has to cover.
CITING = (
    "coefficient-mass-attainment.tex",
    "index.md",
    "polynomial.md",
    "polynomial.tex",
)

#: A numbered reference in running text or in a ``\cite`` option.
_REFERENCE = re.compile(
    r"(Theorem|Lemma|Corollary|Proposition)[~ ]+(\d+\.\d+)",
)

#: The paper a line cites: the key of its ``\cite``, or -- in Markdown, which
#: has no ``\cite`` -- the target of its link.
_CITE_KEY = re.compile(r"\\cite\[[^]]*\]\{([^}]*)\}")
_LINK_KEY = re.compile(r"\]\(([^)]*)\.tex\)")

#: ``\begin{corollary}[Title]`` and the ``\label`` that follows it, which may
#: sit on the next line (``prop:subtwo`` does).
_BEGIN = re.compile(r"\\begin\{(" + "|".join(ENVIRONMENTS) + r")\}(?:\[([^]]*)\])?")
_LABEL = re.compile(r"\\label\{([^}]*)\}")
_SECTION = re.compile(r"^\\section\{")


def _numbering(paper: str) -> dict[str, tuple[str, str, str]]:
    """Map each result number of ``paper`` to the result it names.

    The value is ``(word, label, title)``; the numbering is LaTeX's, one
    counter shared across the four environments and reset by ``\\section``.
    """
    lines = (PROOFS / f"{paper}.tex").read_text().splitlines()
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
        # the papers puts anything else between the two.
        label = _LABEL.search(line) or _LABEL.search(lines[index + 1])
        assert label is not None, f"unlabelled result at line {index + 1}"
        numbered[f"{section}.{counter}"] = (
            ENVIRONMENTS[begin.group(1)],
            label.group(1),
            begin.group(2) or "",
        )
    return numbered


def _cited(name: str) -> set[tuple[str, str, str]]:
    """The ``(word, paper, number)`` references to a companion ``name`` makes.

    The paper is the key the line's own ``\\cite`` names, or the ``.tex`` link
    target in Markdown.  A numbered reference on a line that names neither is
    the file's reference to itself; one whose key is not a paper in
    ``docs/proofs`` is somebody else's, which is what skips the two
    ``Theorem~4.1`` citations of Karlin and Studden.
    """
    found: set[tuple[str, str, str]] = set()
    for line in (PROOFS / name).read_text().splitlines():
        cite = _CITE_KEY.search(line) or _LINK_KEY.search(line)
        if cite is None or not (PROOFS / f"{cite.group(1)}.tex").exists():
            continue
        for match in _REFERENCE.finditer(line):
            found.add((match.group(1), cite.group(1), match.group(2)))
    return found


@pytest.mark.parametrize(("citation", "expected"), sorted(CITATIONS.items()))
def test_citation_resolves(
    citation: tuple[str, str, str], expected: tuple[str, str]
) -> None:
    """Each cited number is the labelled result of the paper it names."""
    _, paper, number = citation
    numbering = _numbering(paper)
    assert number in numbering, f"{paper} has no result {number}"
    word, label, _ = numbering[number]
    assert (word, label) == expected


def test_every_citation_is_covered() -> None:
    """No file cites a companion by a number this table does not list."""
    for name in CITING:
        listed = {
            (word, paper, number)
            for (file, paper, number), (word, _) in CITATIONS.items()
            if file == name
        }
        assert _cited(name) == listed, name


def test_the_cited_titles_are_the_ones_the_papers_name() -> None:
    """The bibliography entry's parenthetical names Corollary 3.4's title."""
    assert _numbering("coefficient-mass")["3.4"][2] == "Logarithmic mass"
    assert _numbering("coefficient-mass")["4.1"][2] == (
        "The bound for $b_2$ at roots $(2,3)$ is an infimum"
    )
    assert _numbering("coefficient-mass-attainment")["2.1"][2] == "Confluent analogue"
    # Compared with whitespace collapsed: the entry is prose, and rewrapping
    # it to fit the margin (``1ab35a6d``) moved the parenthetical onto the
    # line above without changing what it names.
    bibliography = " ".join((PROOFS / "polynomial.tex").read_text().split())
    assert "Corollary~3.4 (Logarithmic mass)" in bibliography
